"""OCP standalone-viewer utilities shared by preview and configurator."""

import asyncio
import logging
import socket
import threading
import time
from urllib.parse import urlparse, urlunparse

_log = logging.getLogger("partomatic")
_viewer_threads: dict[str, threading.Thread] = {}


def _viewer_embed_url(viewer_url: str) -> str:
    """Return iframe-friendly viewer URL, appending `/viewer` when needed."""
    parsed = urlparse(viewer_url)
    path = parsed.path or ""
    if path in ("", "/"):
        return urlunparse(parsed._replace(path="/viewer"))
    return viewer_url


def _is_endpoint_reachable(host: str, port: int, timeout: float = 0.25) -> bool:
    """Return whether a TCP endpoint is reachable within timeout."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _start_ocp_viewer(host: str, port: int):
    """Start standalone OCP viewer thread unless already running."""
    key = f"{host}:{port}"
    existing = _viewer_threads.get(key)
    if existing is not None and existing.is_alive():
        return

    def run_server():
        from ocp_vscode.standalone import Viewer

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            Viewer({"host": host, "port": port}).start()
        except SystemExit:
            pass
        except Exception:
            _log.exception("OCP standalone viewer on %s:%s failed to start", host, port)
        finally:
            loop.close()

    thread = threading.Thread(
        target=run_server,
        daemon=True,
        name=f"ocp-vscode-standalone-{host}-{port}",
    )
    thread.start()
    _viewer_threads[key] = thread


def _ensure_viewer_running(
    viewer_url: str, wait_timeout: float = 10.0, poll_interval: float = 0.2
):
    """Ensure standalone viewer is reachable, starting it if necessary."""
    parsed = urlparse(viewer_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 3939
    if _is_endpoint_reachable(host, port):
        return
    _start_ocp_viewer(host, port)
    deadline = time.monotonic() + wait_timeout
    while time.monotonic() < deadline:
        if _is_endpoint_reachable(host, port):
            _log.info("OCP viewer ready at %s:%s", host, port)
            return
        time.sleep(poll_interval)
    _log.warning(
        "OCP viewer at %s:%s did not become reachable within %.1fs",
        host,
        port,
        wait_timeout,
    )
