"""Tiny path-based reverse proxy.

Routes:
  /api/v1/*  -> http://127.0.0.1:8000/api/v1/*   (FastAPI API router, prefix preserved)
  /v1/*      -> http://127.0.0.1:8000/v1/*       (OpenAI-compat endpoints, prefix preserved)
  /*          -> http://127.0.0.1:3000/*           (Next.js frontend)

Runs on 127.0.0.1:7000. Tailscale Funnel points at this port so a single
public listener can fan out by path — Tailscale Serve/Funnel's
`--set-path` strips the mount prefix, which would break the FastAPI
prefix-based routing.

Started by scripts/start-reverse-proxy.ps1 and supervised by the
watchdog alongside the backend.
"""
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BACKEND = "http://127.0.0.1:8000"
FRONTEND = "http://127.0.0.1:3000"
LISTEN = ("127.0.0.1", 7000)

# Headers we should NOT forward — they describe the inbound connection
# and will be re-set by urlopen.
SKIP_REQUEST_HEADERS = {
    "host", "content-length", "transfer-encoding", "connection",
    "expect", "upgrade",
}
# Headers we should NOT copy back verbatim — they describe the upstream
# hop and must be regenerated for our own response.
SKIP_RESPONSE_HEADERS = {
    "transfer-encoding", "connection", "keep-alive", "proxy-authenticate",
    "proxy-authorization", "te", "trailers", "upgrade",
}


def _hop_by_hop(h: str) -> bool:
    return h.lower() in SKIP_REQUEST_HEADERS


class ProxyHandler(BaseHTTPRequestHandler):
    # Silence default access log; we do our own one-liner.
    def log_message(self, fmt, *args):
        sys.stderr.write("[proxy] %s - %s\n" % (self.address_string(), fmt % args))

    def _proxy(self, method: str):
        path = self.path
        # Backend routes: FastAPI's /api/v1 (app/api/v1.py), the parallel
        # OpenAI-compat surface at /v1 (app/api/v1_compat.py +
        # v1_products.py), and the top-level /health endpoint. Forward the
        # full path so the include_router prefixes match.
        if (path.startswith("/api/v1")
                or path.startswith("/v1/")
                or path == "/health"
                or path.startswith("/health?")):
            target = BACKEND + path
        else:
            target = FRONTEND + path

        # Build upstream request, copying safe headers.
        body = None
        if method in ("POST", "PUT", "PATCH", "DELETE") and "Content-Length" in self.headers:
            try:
                length = int(self.headers["Content-Length"])
                body = self.rfile.read(length) if length > 0 else None
            except (ValueError, OSError):
                body = None
        req = Request(target, data=body, method=method)
        for h, v in self.headers.items():
            if not _hop_by_hop(h):
                req.add_header(h, v)

        try:
            with urlopen(req, timeout=120) as resp:
                self.send_response(resp.status)
                for h, v in resp.getheaders():
                    if h.lower() not in SKIP_RESPONSE_HEADERS:
                        self.send_header(h, v)
                payload = resp.read()
                self.end_headers()
                if payload:
                    self.wfile.write(payload)
        except HTTPError as e:
            # Re-emit upstream 4xx/5xx body so the client sees the real message.
            try:
                self.send_response(e.code)
                for h, v in e.headers.items():
                    if h.lower() not in SKIP_RESPONSE_HEADERS:
                        self.send_header(h, v)
                err_body = e.read()
                self.end_headers()
                if err_body:
                    self.wfile.write(err_body)
            except Exception:
                self.send_error(502, "upstream error")
        except URLError as e:
            self.send_error(502, f"upstream unreachable: {e.reason}")
        except Exception as e:
            self.send_error(502, f"proxy error: {e}")

    def do_GET(self):    self._proxy("GET")
    def do_POST(self):   self._proxy("POST")
    def do_PUT(self):    self._proxy("PUT")
    def do_PATCH(self):  self._proxy("PATCH")
    def do_DELETE(self): self._proxy("DELETE")
    def do_HEAD(self):   self._proxy("HEAD")
    def do_OPTIONS(self): self._proxy("OPTIONS")


def main():
    server = ThreadingHTTPServer(LISTEN, ProxyHandler)
    sys.stderr.write(
        f"[proxy] listening on {LISTEN[0]}:{LISTEN[1]}  "
        f"(api/v1 + /v1 -> {BACKEND}, /* -> {FRONTEND})\n"
    )
    sys.stderr.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
