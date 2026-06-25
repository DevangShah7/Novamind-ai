"""
NovaMind terminal CLI.

A real REPL that talks to the FastAPI backend over HTTP. The web UI uses
the same REST contract, so the CLI is a thin alternative entry point.

Why a CLI and not just the web UI? The user asked for a terminal way to
"run our AI model". This REPL gives them:

  - Login with --user / --password (token cached to ~/.novamind/token)
  - Slash commands: /help, /clear, /history, /model, /new, /chats, /quit
  - Word-by-word reply rendering (so it feels like streaming, even though
    the current backend returns a single JSON response)
  - Ctrl+C cancels the current reply without exiting the REPL
  - Conversation history mirrored to ~/.novamind/history.json for /history
  - Color via `rich` if available, ANSI fallback otherwise
  - No third-party AI calls — the backend runs our own NovaMindLocal engine

Run with:  python -m backend.cli chat --user admin@novamind.ai --password admin123
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from .api_client import NovaMindClient, DEFAULT_BASE_URL

# ---------- color ----------

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt
    _HAS_RICH = True
except Exception:  # pragma: no cover — rich is optional
    _HAS_RICH = False


class _Ansi:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"
    RED = "\033[31m"


def _enable_windows_vt() -> None:
    """Enable ANSI escape sequences on Windows 10+ cmd/PowerShell.

    Best-effort. On older Windows or when not a tty, this is a no-op and the
    user gets uncoloured output, which is still perfectly readable.
    """
    if os.name != "nt":
        return
    try:
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x4
        for handle_id in (-11, -12):  # STDOUT, STDERR
            handle = kernel32.GetStdHandle(handle_id)
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                kernel32.SetConsoleMode(handle, mode.value | 0x4)
    except Exception:
        pass


# ---------- history persistence ----------

_HISTORY_PATH = Path.home() / ".novamind" / "history.json"


def _load_history() -> List[Dict[str, Any]]:
    if not _HISTORY_PATH.exists():
        return []
    try:
        return json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []


def _save_history(entries: List[Dict[str, Any]]) -> None:
    try:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _HISTORY_PATH.write_text(
            json.dumps(entries, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass  # best-effort; the REPL still works without disk persistence.


# ---------- REPL ----------

HELP_TEXT = """\
NovaMind local-engine CLI

Slash commands:
  /help             Show this help
  /clear            Clear the screen
  /history          Show recent exchanges from this session
  /chats            List chats on the backend
  /new [title]      Start a fresh chat (with optional title)
  /model            Show which engine is serving replies
  /logout           Clear cached token and exit
  /quit             Exit the REPL

Anything else is sent as a message to the current chat.
Press Ctrl+C while a reply is streaming to cancel just that reply.
Press Ctrl+D (or Ctrl+C on an empty line) to exit.
"""


class Repl:
    def __init__(self, client: NovaMindClient, model_name: str = "NovaMind-local-v1"):
        self.client = client
        self.model_name = model_name
        self.chat_id: Optional[int] = None
        self.history: List[Dict[str, Any]] = _load_history()
        self.user_label = "you"
        self.bot_label = "novamind"
        self._stream_cancel = False
        if _HAS_RICH:
            self.console = Console()
        else:
            self.console = None  # type: ignore[assignment]

    # ---------- printing helpers ----------

    def _print(self, text: str, *, style: str = "") -> None:
        if self.console is not None:
            self.console.print(text, style=style)
        else:
            sys.stdout.write((style + text + _Ansi.RESET) if style else text)
            sys.stdout.write("\n")
            sys.stdout.flush()

    def _print_inline(self, text: str) -> None:
        if self.console is not None:
            self.console.print(text, end="")
        else:
            sys.stdout.write(text)
            sys.stdout.flush()

    def _rule(self, label: str = "") -> None:
        if self.console is not None:
            self.console.rule(label)
        else:
            width = 60
            line = "-" * max(0, (width - len(label) - 2) // 2)
            sys.stdout.write(f"{_Ansi.DIM}{line} {label} {line}{_Ansi.RESET}\n")
            sys.stdout.flush()

    # ---------- banner ----------

    def _banner(self) -> None:
        tagline = (
            "NovaMind local engine - a rule-based response engine, "
            "not a foundation model. No external API calls."
        )
        if self.console is not None:
            self.console.print(
                Panel(tagline, title="novamind cli", border_style="cyan")
            )
        else:
            # ASCII-only banner so we don't choke on cp1252 (Windows cmd) or
            # terminals without UTF-8. Coloured where the terminal supports it.
            self._print(f"{_Ansi.BOLD}{_Ansi.CYAN}=== novamind cli ==={_Ansi.RESET}")
            self._print(f"{_Ansi.DIM}{tagline}{_Ansi.RESET}")
        self._print(f"backend: {self.client.base_url}")
        self._print(f"engine:  {self.model_name}")
        self._print("type /help for commands, /quit to exit\n")

    # ---------- prompt ----------

    def _prompt(self) -> str:
        if self.console is not None:
            return Prompt.ask(f"[bold cyan]{self.user_label}[/bold cyan]")
        try:
            return input(f"{_Ansi.BOLD}{_Ansi.CYAN}{self.user_label}{_Ansi.RESET}> ")
        except EOFError:
            return "/quit"

    # ---------- streaming render ----------

    def _stream_reply(self, text: str, per_word_delay: float = 0.015) -> None:
        """Print the assistant reply word-by-word.

        The backend returns a single string; we render it in chunks so the
        user sees the same streaming UX the web UI gives them.
        """
        self._stream_cancel = False
        words = text.split(" ")
        for i, word in enumerate(words):
            if self._stream_cancel:
                self._print(f" {_Ansi.DIM}…cancelled{_Ansi.RESET}")
                return
            chunk = word if i == 0 else " " + word
            self._print_inline(chunk)
            # Honour Ctrl+C without losing the line we've started.
            time.sleep(per_word_delay)
        # Newline so the next prompt isn't on the same line.
        sys.stdout.write("\n")
        sys.stdout.flush()

    # ---------- backend interaction ----------

    def _ensure_chat(self, title: str = "cli-session") -> int:
        if self.chat_id is not None:
            return self.chat_id
        chat = self.client.create_chat(title=title)
        self.chat_id = int(chat["id"])
        return self.chat_id

    def _send(self, content: str) -> str:
        chat_id = self._ensure_chat()
        msg = self.client.send_message(chat_id=chat_id, content=content)
        return str(msg.get("content", ""))

    # ---------- commands ----------

    def _cmd_help(self) -> None:
        self._print(HELP_TEXT)

    def _cmd_clear(self) -> None:
        if self.console is not None:
            self.console.clear()
        else:
            sys.stdout.write("\033[2J\033[H")
            sys.stdout.flush()

    def _cmd_history(self) -> None:
        if not self.history:
            self._print("(no exchanges yet in this REPL session)")
            return
        for entry in self.history[-20:]:
            self._print(
                f"{_Ansi.DIM}[{entry.get('ts', '?')}]{_Ansi.RESET} "
                f"{_Ansi.CYAN}{self.user_label}{_Ansi.RESET}: {entry['user']}"
            )
            self._print(
                f"  {_Ansi.MAGENTA}{self.bot_label}{_Ansi.RESET}: {entry['assistant']}"
            )

    def _cmd_chats(self) -> None:
        try:
            chats = self.client.list_chats()
        except Exception as e:
            self._print(f"{_Ansi.RED}error:{_Ansi.RESET} {e}")
            return
        if not chats:
            self._print("(no chats on the backend)")
            return
        for c in chats:
            cid = c.get("id")
            title = c.get("title") or "(untitled)"
            last = c.get("last_message_at") or ""
            self._print(f"  {cid:>4}  {title}  {_Ansi.DIM}{last}{_Ansi.RESET}")

    def _cmd_new(self, args: List[str]) -> None:
        title = " ".join(args).strip() or "cli-session"
        try:
            chat = self.client.create_chat(title=title)
        except Exception as e:
            self._print(f"{_Ansi.RED}error:{_Ansi.RESET} {e}")
            return
        self.chat_id = int(chat["id"])
        self._print(f"started new chat: {self.chat_id} ({title})")

    def _cmd_model(self) -> None:
        self._print(f"engine: {self.model_name}")
        self._print(f"backend: {self.client.base_url}")

    def _cmd_logout(self) -> None:
        self.client.clear_token()
        self._print("token cleared. bye.")
        sys.exit(0)

    # ---------- main loop ----------

    def run(self) -> int:
        self._banner()
        self._cmd_help()
        while True:
            try:
                line = self._prompt()
            except KeyboardInterrupt:
                # Ctrl+C on an empty line exits; mid-stream it cancels the reply.
                if not sys.stdout.isatty():
                    self._print("")
                self._print("bye.")
                return 0
            line = line.strip()
            if not line:
                continue

            if line.startswith("/"):
                parts = line.split()
                cmd, args = parts[0].lower(), parts[1:]
                if cmd in ("/quit", "/exit", ":q"):
                    self._print("bye.")
                    return 0
                if cmd == "/help":
                    self._cmd_help()
                elif cmd == "/clear":
                    self._cmd_clear()
                elif cmd == "/history":
                    self._cmd_history()
                elif cmd == "/chats":
                    self._cmd_chats()
                elif cmd == "/new":
                    self._cmd_new(args)
                elif cmd == "/model":
                    self._cmd_model()
                elif cmd == "/logout":
                    self._cmd_logout()
                else:
                    self._print(f"{_Ansi.YELLOW}unknown command:{_Ansi.RESET} {cmd}")
                    self._print("type /help for the list")
                continue

            # Real message — send and stream the reply.
            self._rule("send")
            self._print(f"{_Ansi.CYAN}{self.user_label}{_Ansi.RESET}: {line}")
            self._rule("")
            try:
                # Install a SIGINT handler that just flips a flag, so the user
                # can cancel a long reply without leaving the REPL.
                previous = signal.getsignal(signal.SIGINT)
                signal.signal(signal.SIGINT, self._on_sigint)
                self._stream_cancel = False
                try:
                    reply = self._send(line)
                finally:
                    signal.signal(signal.SIGINT, previous)
            except KeyboardInterrupt:
                self._print(f"\n{_Ansi.YELLOW}cancelled before send completed{_Ansi.RESET}")
                continue
            except Exception as e:
                self._print(f"{_Ansi.RED}error:{_Ansi.RESET} {e}")
                continue

            self._print_inline(f"{_Ansi.MAGENTA}{self.bot_label}{_Ansi.RESET}: ")
            try:
                previous = signal.getsignal(signal.SIGINT)
                signal.signal(signal.SIGINT, self._on_sigint)
                self._stream_cancel = False
                self._stream_reply(reply)
            except KeyboardInterrupt:
                self._print(f"\n{_Ansi.YELLOW}cancelled{_Ansi.RESET}")
            finally:
                signal.signal(signal.SIGINT, previous)

            entry = {
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "user": line,
                "assistant": reply,
                "engine": self.model_name,
            }
            self.history.append(entry)
            _save_history(self.history)

    def _on_sigint(self, signum, frame):  # noqa: ARG002
        # Setting the flag is enough; the streaming loop checks it each word.
        self._stream_cancel = True


# ---------- CLI entrypoint ----------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="novamind",
        description="NovaMind local-engine CLI. Talks to the FastAPI backend over HTTP.",
    )
    p.add_argument(
        "--api-url",
        default=os.environ.get("NOVAMIND_API_URL", DEFAULT_BASE_URL),
        help=f"Backend base URL (default: {DEFAULT_BASE_URL})",
    )
    p.add_argument("--user", help="Email to log in with (skips interactive prompt)")
    p.add_argument("--password", help="Password to log in with (skips interactive prompt)")
    p.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colour output (also honoured if NO_COLOR is set)",
    )
    sub = p.add_subparsers(dest="cmd")

    chat = sub.add_parser("chat", help="Open the interactive REPL (default if no subcommand)")
    chat.add_argument("--title", default="cli-session", help="Title for the auto-created chat")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    if os.environ.get("NO_COLOR") or args.no_color:
        global _HAS_RICH
        _HAS_RICH = False
    else:
        _enable_windows_vt()

    cmd = args.cmd or "chat"
    if cmd != "chat":
        print(f"unknown subcommand: {cmd}", file=sys.stderr)
        return 2

    client = NovaMindClient(base_url=args.api_url)

    # Login. Prefer cached token; fall back to --user/--password; finally prompt.
    if not client.token:
        email = args.user
        password = args.password
        if not email or not password:
            if not _HAS_RICH:
                # Plain-input fallback so the CLI still works without rich.
                try:
                    email = email or input("email: ")
                    import getpass
                    password = password or getpass.getpass("password: ")
                except (EOFError, KeyboardInterrupt):
                    print("\naborted.", file=sys.stderr)
                    return 1
            else:
                from rich.prompt import Prompt
                from rich.console import Console as _C
                _c = _C()
                email = email or _c.input("email: ")
                password = password or _c.input("password: ", password=True)
        try:
            client.login(email=email, password=password)
        except Exception as e:
            print(f"login failed: {e}", file=sys.stderr)
            return 1
        print(f"logged in as {email}")

    repl = Repl(client=client)
    if hasattr(args, "title") and args.title:
        # Pre-create the chat so the user can see the chat id up front.
        try:
            repl._ensure_chat(title=args.title)
        except Exception as e:
            print(f"warning: could not pre-create chat: {e}", file=sys.stderr)
    try:
        return repl.run()
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
