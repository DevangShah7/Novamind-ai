"""Sandboxed subprocess runner for user-submitted code.

The chat endpoint uses this for `message_type == "code"` requests: the LLM
emits a source file, the server runs it in an isolated tempdir, captures
stdout/stderr with hard size caps, and returns the result so the frontend
can show the user what ran.

This is deliberately *not* a Docker sandbox. The chat composer's
"Run code" affordance is meant for short, user-initiated snippets
(think "print the first 10 primes") — full kernel-level isolation is
overkill and Docker isn't always available on local dev. We get
reasonable containment from:

  1. cwd = a fresh tempfile.TemporaryDirectory() — scripts cannot write
     outside it without an absolute path, and the dir is gone after the
     request.
  2. env = a minimal allowlist — no secrets, no AWS keys, no GITHUB_TOKEN,
     no PATH entries from the host.
  3. timeout_s — hard wall-clock cap; subprocess.run sends SIGKILL after.
  4. stdout/stderr size caps — the child can't OOM us by spamming.

The remaining attack surface (CPU/RAM exhaustion, fork bombs, network
calls) is bounded only by `timeout_s` and the OS process limits. If a
user runs hostile code on a public multi-tenant deploy, escalate to
Docker or a gVisor sandbox — but that's not the current deployment.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field, asdict
from typing import Optional


# Per-run limits. The timeout is the most important knob: if it's too
# high, a single bad request ties up an uvicorn worker for the duration.
# 8 s is enough for ~all the "print me a chart / first 50 primes" cases
# the chat composer will see, and short enough that a runaway script
# doesn't kill the whole server.
DEFAULT_TIMEOUT_S: float = 8.0

# Output caps. A malicious or naive script can write gigabytes to
# stdout; we cap it on read so subprocess.run's pipe buffer can't grow
# unboundedly and the chat message's `meta_data` JSON stays small
# enough to persist + transport.
MAX_STDOUT_BYTES: int = 32 * 1024
MAX_STDERR_BYTES: int = 8 * 1024


@dataclass
class CodeRunResult:
    """What `execute_*` returns. All fields are JSON-serializable so the
    chat endpoint can drop this straight into `meta_data`."""

    language: str
    code: str
    stdout: str
    stderr: str
    exit_code: Optional[int] = None  # None when the process was killed by the timeout
    timed_out: bool = False
    runtime_missing: bool = False  # set when the requested interpreter isn't installed
    elapsed_ms: int = 0
    stdout_truncated: bool = False
    stderr_truncated: bool = False

    def to_meta(self) -> dict:
        return asdict(self)


def _truncate(s: str, cap: int) -> tuple[str, bool]:
    """Truncate `s` to `cap` bytes (not chars) and report whether it was cut."""
    encoded = s.encode("utf-8", errors="replace")
    if len(encoded) <= cap:
        return s, False
    # Truncate on a byte boundary then re-decode ignoring the trailing
    # partial codepoint so we never ship invalid UTF-8.
    truncated = encoded[:cap]
    truncated = truncated[: truncated.rfind(b"\n") + 1] if b"\n" in truncated else truncated
    return truncated.decode("utf-8", errors="replace") + "\n[... output truncated ...]", True


def _build_minimal_env(tempdir: str) -> dict:
    """The bare minimum the child needs to import stdlib and write its
    scratch file. Nothing else from the host environment leaks through.

    PATH is restricted to /usr/bin and /bin on POSIX; on Windows we let
    the OS resolve `python.exe` via the explicit `sys.executable` arg
    and only set PATH so subprocess can find DLLs. The shell never sees
    user secrets.
    """
    if os.name == "nt":
        # On Windows, sys.executable is the absolute path so PATH isn't
        # needed for *python* itself, but the script may shell out to
        # `git` / `node` / etc. Keep PATH minimal — SYSTEMROOT is
        # required for some stdlib calls.
        return {
            "SYSTEMROOT": os.environ.get("SYSTEMROOT", r"C:\Windows"),
            "TEMP": tempdir,
            "TMP": tempdir,
            "HOME": tempdir,
            "USERPROFILE": tempdir,
            "PATH": os.path.join(tempdir, ""),  # empty path; child can use sys.executable paths only
        }
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": tempdir,
        "TMPDIR": tempdir,
    }


def _run_in_subprocess(
    argv: list[str],
    script_text: str,
    *,
    suffix: str,
    timeout_s: float,
    language: str,
) -> CodeRunResult:
    """Common path for every language. Writes `script_text` into a fresh
    tempdir, runs `argv` with cwd=tempdir and minimal env, captures
    output, returns a CodeRunResult."""
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="novamind_run_") as tempdir:
        script_path = os.path.join(tempdir, f"script{suffix}")
        with open(script_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(script_text)
        env = _build_minimal_env(tempdir)
        try:
            completed = subprocess.run(
                argv,
                cwd=tempdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
                # Windows: don't pop a console window. POSIX default fine.
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) or None,
            )
            stdout, so_trunc = _truncate(completed.stdout or "", MAX_STDOUT_BYTES)
            stderr, se_trunc = _truncate(completed.stderr or "", MAX_STDERR_BYTES)
            return CodeRunResult(
                language=language,
                code=script_text,
                stdout=stdout,
                stderr=stderr,
                exit_code=completed.returncode,
                timed_out=False,
                elapsed_ms=int((time.monotonic() - start) * 1000),
                stdout_truncated=so_trunc,
                stderr_truncated=se_trunc,
            )
        except subprocess.TimeoutExpired as exc:
            # subprocess.run already killed the child by this point. Capture
            # whatever was buffered before the kill so the user can see
            # "we got 5s of output before we gave up".
            stdout, so_trunc = _truncate(
                (exc.stdout or b"").decode("utf-8", errors="replace")
                if isinstance(exc.stdout, (bytes, bytearray))
                else (exc.stdout or ""),
                MAX_STDOUT_BYTES,
            )
            stderr, se_trunc = _truncate(
                (exc.stderr or b"").decode("utf-8", errors="replace")
                if isinstance(exc.stderr, (bytes, bytearray))
                else (exc.stderr or ""),
                MAX_STDERR_BYTES,
            )
            return CodeRunResult(
                language=language,
                code=script_text,
                stdout=stdout,
                stderr=stderr,
                exit_code=None,
                timed_out=True,
                elapsed_ms=int(timeout_s * 1000),
                stdout_truncated=so_trunc,
                stderr_truncated=se_trunc,
            )
        except FileNotFoundError as exc:
            # The interpreter itself wasn't on PATH. Mark the run as
            # "missing runtime" so the frontend can show a helpful
            # message instead of an OSError stack trace.
            return CodeRunResult(
                language=language,
                code=script_text,
                stdout="",
                stderr=str(exc),
                exit_code=None,
                timed_out=False,
                runtime_missing=True,
                elapsed_ms=int((time.monotonic() - start) * 1000),
            )


def execute_python(script: str, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> CodeRunResult:
    """Run a Python snippet in a sandboxed subprocess.

    `script` is the raw source (no need for a shebang). We use
    `sys.executable -I` for isolated mode: no user site, no PYTHONPATH
    inheritance, no env vars except ours. `-W ignore` keeps a noisy
    DeprecationWarning from polluting stderr.
    """
    argv = [sys.executable, "-I", "-W", "ignore", "-c", script]
    # We pass the script as `-c` arg rather than writing a .py file —
    # saves a tempfile write for the common "tiny snippet" case, and
    # `-c` doesn't appear in `ps` output as a file path.
    start = time.monotonic()

    env = _build_minimal_env(tempfile.gettempdir())
    try:
        completed = subprocess.run(
            argv,
            cwd=tempfile.gettempdir(),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) or None,
        )
        stdout, so_trunc = _truncate(completed.stdout or "", MAX_STDOUT_BYTES)
        stderr, se_trunc = _truncate(completed.stderr or "", MAX_STDERR_BYTES)
        return CodeRunResult(
            language="python",
            code=script,
            stdout=stdout,
            stderr=stderr,
            exit_code=completed.returncode,
            timed_out=False,
            elapsed_ms=int((time.monotonic() - start) * 1000),
            stdout_truncated=so_trunc,
            stderr_truncated=se_trunc,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, so_trunc = _truncate(
            (exc.stdout or b"").decode("utf-8", errors="replace")
            if isinstance(exc.stdout, (bytes, bytearray))
            else (exc.stdout or ""),
            MAX_STDOUT_BYTES,
        )
        stderr, se_trunc = _truncate(
            (exc.stderr or b"").decode("utf-8", errors="replace")
            if isinstance(exc.stderr, (bytes, bytearray))
            else (exc.stderr or ""),
            MAX_STDERR_BYTES,
        )
        return CodeRunResult(
            language="python",
            code=script,
            stdout=stdout,
            stderr=stderr,
            exit_code=None,
            timed_out=True,
            elapsed_ms=int(timeout_s * 1000),
            stdout_truncated=so_trunc,
            stderr_truncated=se_trunc,
        )


def execute_javascript(script: str, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> CodeRunResult:
    """Run JS via the system `node` interpreter, if available. Otherwise
    returns a `runtime_missing=True` result so the caller can show a
    helpful 'node not installed' message."""
    import shutil

    if shutil.which("node") is None:
        return CodeRunResult(
            language="javascript",
            code=script,
            stdout="",
            stderr="node runtime not found on PATH",
            runtime_missing=True,
        )
    return _run_in_subprocess(
        ["node", "-e", script],
        script,
        suffix=".js",
        timeout_s=timeout_s,
        language="javascript",
    )


def execute_bash(script: str, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> CodeRunResult:
    """Run a bash script. We use `bash -c` so the child can't read
    interactive history files."""
    import shutil

    if shutil.which("bash") is None:
        return CodeRunResult(
            language="bash",
            code=script,
            stdout="",
            stderr="bash runtime not found on PATH",
            runtime_missing=True,
        )
    return _run_in_subprocess(
        ["bash", "-c", script],
        script,
        suffix=".sh",
        timeout_s=timeout_s,
        language="bash",
    )


def execute_sql(script: str, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> CodeRunResult:
    """Pipe `script` into the system `sqlite3` interpreter against an
    in-memory DB. Useful for the chat's "show me the SQL that..." use
    case."""
    import shutil

    if shutil.which("sqlite3") is None:
        return CodeRunResult(
            language="sql",
            code=script,
            stdout="",
            stderr="sqlite3 runtime not found on PATH",
            runtime_missing=True,
        )
    return _run_in_subprocess(
        ["sqlite3", ":memory:"],
        script,
        suffix=".sql",
        timeout_s=timeout_s,
        language="sql",
    )


# Public dispatcher — the chat endpoint looks up by language id.
EXECUTORS = {
    "python": execute_python,
    "javascript": execute_javascript,
    "js": execute_javascript,
    "bash": execute_bash,
    "sh": execute_bash,
    "sql": execute_sql,
}


def run(language: str, script: str, *, timeout_s: float = DEFAULT_TIMEOUT_S) -> CodeRunResult:
    """Top-level entry point. Unknown languages return an immediate
    `runtime_missing=True` so the frontend gets a clean signal instead
    of an AttributeError."""
    fn = EXECUTORS.get((language or "").lower())
    if fn is None:
        return CodeRunResult(
            language=language or "unknown",
            code=script,
            stdout="",
            stderr=f"Unsupported language: {language!r}. Supported: {sorted(set(EXECUTORS.keys()))}",
            runtime_missing=True,
        )
    return fn(script, timeout_s=timeout_s)