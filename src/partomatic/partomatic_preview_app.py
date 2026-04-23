"""NiceGUI preview shell for Partomatic objects."""

import socket
import threading
from urllib.parse import urlparse, urlunparse
from pathlib import Path

import ocp_vscode
from nicegui import ui


from partomatic.partomatic_preview import PreviewState


_viewer_threads: dict[str, threading.Thread] = {}


def _viewer_embed_url(viewer_url: str) -> str:
    parsed = urlparse(viewer_url)
    path = parsed.path or ""

    if path in ("", "/"):
        return urlunparse(parsed._replace(path="/viewer"))

    return viewer_url


def _is_endpoint_reachable(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _start_ocp_viewer(host: str, port: int):
    key = f"{host}:{port}"
    existing = _viewer_threads.get(key)
    if existing is not None and existing.is_alive():
        return

    def run_server():
        from ocp_vscode.standalone import Viewer

        try:
            Viewer({"host": host, "port": port}).start()
        except SystemExit:
            return

    thread = threading.Thread(
        target=run_server,
        daemon=True,
        name=f"ocp-vscode-standalone-{host}-{port}",
    )
    thread.start()
    _viewer_threads[key] = thread


def _ensure_viewer_running(viewer_url: str):
    parsed = urlparse(viewer_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 3939
    if not _is_endpoint_reachable(host, port):
        _start_ocp_viewer(host, port)


def run_preview(partomatic, spec: dict, host: str = "localhost", port: int = 8503):
    class_name = spec.get("class_name", "Partomatic")
    viewer_url = spec.get("viewer_url", "http://127.0.0.1:3939")
    _ensure_viewer_running(viewer_url)

    def build_ui():
        with ui.column().classes("w-full max-w-7xl mx-auto p-6 gap-4"):
            ui.label(f"{class_name} Preview").classes("text-3xl font-medium")

            with ui.card().classes("w-full"):
                ui.element("iframe").props(
                    f'src="{viewer_url}" title="OCP Viewer"'
                ).style("width:100%;height:70vh;border:0;").classes("w-full")

        def render_model():
            try:
                partomatic.compile_for_preview()
                partomatic.display(reset_camera=ocp_vscode.Camera.RESET)
            except Exception:
                pass

        ui.timer(1.5, render_model, once=True)

    ui.run(host=host, port=port, reload=False, show=False, root=build_ui)
