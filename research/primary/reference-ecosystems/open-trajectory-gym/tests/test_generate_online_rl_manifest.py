"""Tests for online RL registry generator."""

from __future__ import annotations

import socket
import threading

from trajgym.cli.generate_online_rl import _is_reachable


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_probe_target_requires_http_response_for_http_urls() -> None:
    import socketserver

    class DropHandler(socketserver.BaseRequestHandler):
        def handle(self) -> None:  # pragma: no cover - network callback
            # Accept then immediately close without HTTP response.
            return

    port = _free_port()
    server = socketserver.TCPServer(("127.0.0.1", port), DropHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ok = _is_reachable(f"http://127.0.0.1:{port}", category="web", timeout=0.8)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)
    assert ok is False


def test_probe_target_accepts_real_http_server() -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class OkHandler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - stdlib signature
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, fmt, *args):  # pragma: no cover - silence test logs
            return

    port = _free_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), OkHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ok = _is_reachable(f"http://127.0.0.1:{port}", category="web", timeout=1.0)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)
    assert ok is True
