"""
Tiny httpx wrapper for the CLI. Speaks the same REST contract the web UI uses.

Why httpx and not the openapi client? The CLI is meant to work against any
NovaMind backend (local, dev, prod) without code-gen steps. A 50-line
wrapper keeps it dead simple.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

DEFAULT_BASE_URL = os.environ.get("NOVAMIND_API_URL", "http://localhost:8000/api/v1")
DEFAULT_TIMEOUT = 30.0


class NovaMindClient:
    """Thin REST client. Stores token in ~/.novamind/token by default."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        token_path: Optional[Path] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self.base_url, timeout=DEFAULT_TIMEOUT)
        self.token_path = token_path or (Path.home() / ".novamind" / "token")
        self.token: Optional[str] = None
        self._load_token()

    # ---------- token persistence ----------

    def _load_token(self) -> None:
        try:
            if self.token_path.exists():
                self.token = self.token_path.read_text(encoding="utf-8").strip() or None
        except OSError:
            self.token = None

    def _save_token(self, token: str) -> None:
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            self.token_path.write_text(token, encoding="utf-8")
            # Restrict to owner on POSIX. Windows ignores the mode bits.
            try:
                os.chmod(self.token_path, 0o600)
            except (OSError, AttributeError):
                pass
        except OSError:
            pass  # best-effort; we'll re-prompt next time.

    def clear_token(self) -> None:
        self.token = None
        try:
            if self.token_path.exists():
                self.token_path.unlink()
        except OSError:
            pass

    # ---------- auth ----------

    def login(self, email: str, password: str) -> Dict[str, Any]:
        resp = self._client.post("/auth/login", json={"email": email, "password": password})
        if resp.status_code != 200:
            raise RuntimeError(_extract_error(resp, "login failed"))
        body = resp.json()
        self.token = body["access_token"]
        self._save_token(self.token)
        return body

    def _auth_headers(self) -> Dict[str, str]:
        if not self.token:
            raise RuntimeError("not logged in — run with --user and --password first")
        return {"Authorization": f"Bearer {self.token}"}

    # ---------- chats ----------

    def list_chats(self) -> List[Dict[str, Any]]:
        resp = self._client.get("/chats", headers=self._auth_headers())
        if resp.status_code != 200:
            raise RuntimeError(_extract_error(resp, "list chats failed"))
        return resp.json()

    def create_chat(self, title: str) -> Dict[str, Any]:
        resp = self._client.post("/chats", json={"title": title}, headers=self._auth_headers())
        if resp.status_code != 200:
            raise RuntimeError(_extract_error(resp, "create chat failed"))
        return resp.json()

    def get_messages(self, chat_id: int) -> List[Dict[str, Any]]:
        resp = self._client.get(
            f"/chats/{chat_id}/messages", headers=self._auth_headers()
        )
        if resp.status_code != 200:
            raise RuntimeError(_extract_error(resp, "load messages failed"))
        return resp.json()

    def send_message(self, chat_id: int, content: str) -> Dict[str, Any]:
        resp = self._client.post(
            f"/chats/{chat_id}/messages",
            json={"content": content, "message_type": "text"},
            headers=self._auth_headers(),
        )
        if resp.status_code != 200:
            raise RuntimeError(_extract_error(resp, "send failed"))
        return resp.json()

    def close(self) -> None:
        self._client.close()


def _extract_error(resp: httpx.Response, fallback: str) -> str:
    try:
        body = resp.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
    except (json.JSONDecodeError, ValueError):
        pass
    return f"{fallback} (HTTP {resp.status_code})"
