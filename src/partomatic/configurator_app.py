"""Combined single-window configurator for Partomatic: config editing + live 3D preview."""

__package__ = "partomatic"

if __name__ == "__main__":
    import os, sys

    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_root = os.path.dirname(script_dir)
    # Avoid resolving 'partomatic' to this directory's modules during direct execution.
    if script_dir in sys.path:
        sys.path.remove(script_dir)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

import socket
import io
import inspect
from pathlib import Path
import tempfile
from urllib.parse import urlparse
import zipfile

from nicegui import ui
from pydantic import ValidationError
import yaml

from partomatic.config_editor_app import (
    _build_model,
    _collect_components,
    _component_value,
    _to_yaml_document,
)
from partomatic.partomatic_preview import PreviewState
from partomatic.partomatic_preview_app import (
    _ensure_viewer_running,
    _viewer_embed_url,
)


# ---------------------------------------------------------------------------
# Port utilities
# ---------------------------------------------------------------------------

MAX_PORT_RETRIES = 10


async def _extract_uploaded_text(upload_event) -> str:
    """Extract UTF-8 text content from a NiceGUI upload event.

    Args:
        upload_event: NiceGUI upload event object.

    Returns:
        Uploaded file content as text.

    Raises:
        ValueError: If no readable text content is present.
    """
    file_obj = getattr(upload_event, "file", None)
    if file_obj is not None:
        if hasattr(file_obj, "text"):
            maybe_text = file_obj.text("utf-8")
            if inspect.isawaitable(maybe_text):
                return await maybe_text
            if isinstance(maybe_text, str):
                return maybe_text

        if hasattr(file_obj, "read"):
            maybe_data = file_obj.read()
            raw_data = (
                await maybe_data if inspect.isawaitable(maybe_data) else maybe_data
            )
            if isinstance(raw_data, bytes):
                return raw_data.decode("utf-8")
            if isinstance(raw_data, str):
                return raw_data

    content = getattr(upload_event, "content", None)
    if content is None:
        raise ValueError("Uploaded file content is missing")

    if hasattr(content, "seek"):
        content.seek(0)

    if hasattr(content, "read"):
        raw_data = content.read()
    else:
        raw_data = content

    if isinstance(raw_data, bytes):
        return raw_data.decode("utf-8")
    if isinstance(raw_data, str):
        return raw_data
    raise ValueError("Uploaded file must be text YAML")


def _yaml_to_config_data(yaml_text: str, root_node: str) -> dict:
    """Parse YAML text and return configuration mapping for a root node."""
    parsed = yaml.safe_load(yaml_text)
    if parsed is None:
        raise ValueError("Uploaded YAML is empty")
    if not isinstance(parsed, dict):
        raise ValueError("Uploaded YAML must be a mapping")

    config_data = parsed.get(root_node, parsed)
    if not isinstance(config_data, dict):
        raise ValueError(f"YAML node '{root_node}' must be a mapping")
    return config_data


def _apply_values_to_component_tree(component_tree: dict, values: dict):
    """Apply mapping values recursively into a rendered component tree."""
    for key, value in values.items():
        if key not in component_tree:
            continue
        target = component_tree[key]
        if isinstance(target, dict) and isinstance(value, dict):
            _apply_values_to_component_tree(target, value)
            continue
        if hasattr(target, "value"):
            target.value = value


def _download_payload_from_paths(
    exported_paths: list[Path],
    zip_filename: str,
    single_media_type: str,
) -> tuple[bytes, str, str]:
    """Build download payload bytes for one file or a zipped multi-file export."""
    if not exported_paths:
        raise ValueError("No files were generated for download")
    if len(exported_paths) == 1:
        export_path = exported_paths[0]
        return export_path.read_bytes(), export_path.name, single_media_type

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for export_path in exported_paths:
            archive.write(export_path, arcname=export_path.name)
    return buffer.getvalue(), zip_filename, "application/zip"


def find_available_port(
    host: str = "localhost",
    start_port: int = 8501,
    retries: int = MAX_PORT_RETRIES,
) -> int:
    """Find the first available TCP port in a range.

    Args:
        host: Hostname/interface to test.
        start_port: First port in the candidate range.
        retries: Additional consecutive ports to try.

    Returns:
        The first free port in `[start_port, start_port + retries]`.

    Raises:
        OSError: If no port in the range is available.
    """
    for offset in range(retries + 1):
        port = start_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise OSError(
        f"No free port found in range [{start_port}, {start_port + retries}] on {host}"
    )


# ---------------------------------------------------------------------------
# Combined configurator UI
# ---------------------------------------------------------------------------


def run_configurator(
    partomatic,
    spec: dict,
    host: str = "localhost",
    port: int = 8505,
    port_retries: int = MAX_PORT_RETRIES,
):
    """Launch the combined configurator window.

    Left panel: configuration form (reuses config_editor_app field renderers).
    Right panel: OCP viewer iframe.
    Re-render button: applies config to the Partomatic object and triggers a display.

    Args:
        partomatic: Partomatic instance to configure, compile, preview, and export.
        spec: UI specification containing class name, viewer URL, and config spec.
        host: Hostname/interface for the NiceGUI server.
        port: Preferred starting port for the NiceGUI server.
        port_retries: Additional ports to try if `port` is unavailable.

    Returns:
        None. This function starts the NiceGUI app server.
    """
    class_name = spec.get("class_name", "Partomatic")
    config_spec = spec.get("config_spec", {})
    root_node = config_spec.get("root_node", "config")
    fields_spec = config_spec.get("fields", {})
    viewer_url = spec.get("viewer_url", "http://127.0.0.1:3939")
    embed_url = _viewer_embed_url(viewer_url)
    parsed_viewer_url = urlparse(viewer_url)
    viewer_host = parsed_viewer_url.hostname or "127.0.0.1"
    viewer_port = parsed_viewer_url.port or 3939

    model = _build_model(f"{class_name}EditorModel", fields_spec)

    _ensure_viewer_running(viewer_url)

    port = find_available_port(host=host, start_port=port, retries=port_retries)

    def build_ui():
        ui.page_title("configurator")
        step_download_item = None

        # top bar
        with ui.row().classes("w-full items-center px-6 py-3 bg-slate-800"):
            ui.label("configurator").classes("text-white text-2xl font-semibold")

        form_state = {}

        # main two-column layout
        with ui.row().classes("w-full h-full gap-0"):

            # left column: config form
            with ui.column().classes(
                "w-1/3 p-4 gap-4 overflow-y-auto border-r border-slate-200"
            ):
                ui.label(f"{class_name} Configuration").classes("text-lg font-medium")

                with ui.card().classes("w-full"):
                    component_tree = _collect_components(fields_spec, form_state)

                validation_label = ui.label().classes(
                    "text-red-700 whitespace-pre-wrap text-sm"
                )

                def _current_validated():
                    values = _component_value(component_tree)
                    try:
                        validated = model.model_validate(values)
                        output_data = validated.model_dump(mode="python")
                        validation_label.set_text("")
                        return output_data, True
                    except ValidationError as ex:
                        validation_label.set_text(str(ex))
                        return values, False

                def _enable_step_exports_value(output_data: dict) -> bool:
                    return bool(
                        output_data.get(
                            "enable_step_exports",
                            getattr(partomatic._config, "enable_step_exports", False),
                        )
                    )

                def _sync_export_visibility(output_data: dict):
                    if step_download_item is not None:
                        step_download_item.set_visibility(
                            _enable_step_exports_value(output_data)
                        )

                def _download_yaml():
                    output_data, ok = _current_validated()
                    if not ok:
                        return
                    yaml_text = _to_yaml_document(root_node, output_data)
                    ui.download(
                        yaml_text.encode("utf-8"),
                        filename=f"{root_node}.yaml",
                        media_type="application/x-yaml",
                    )

                def _download_export(kind: str):
                    output_data, ok = _current_validated()
                    if not ok:
                        return
                    try:
                        partomatic._config.update_from_mapping(output_data)
                        partomatic.invalidate_preview()
                        if partomatic.is_dirty:
                            partomatic.compile()
                        partomatic.display(
                            viewer_host=viewer_host,
                            viewer_port=viewer_port,
                        )
                        with tempfile.TemporaryDirectory(
                            prefix=f"partomatic-{kind}-"
                        ) as export_dir:
                            if kind == "stl":
                                exported_paths = partomatic.export_stls_to_directory(
                                    export_dir
                                )
                                payload, filename, media_type = (
                                    _download_payload_from_paths(
                                        [Path(path) for path in exported_paths],
                                        f"{root_node}-stls.zip",
                                        "model/stl",
                                    )
                                )
                            else:
                                exported_paths = partomatic.export_steps_to_directory(
                                    export_dir
                                )
                                payload, filename, media_type = (
                                    _download_payload_from_paths(
                                        [Path(path) for path in exported_paths],
                                        f"{root_node}-steps.zip",
                                        "model/step",
                                    )
                                )
                        ui.download(
                            payload,
                            filename=filename,
                            media_type=media_type,
                        )
                        _sync_overlay_state()
                    except Exception as ex:
                        validation_label.set_text(f"Export error: {ex}")
                        ui.notify(f"Export failed: {ex}", type="negative")

                async def _load_yaml_upload(upload_event):
                    try:
                        yaml_text = await _extract_uploaded_text(upload_event)
                        loaded_data = _yaml_to_config_data(yaml_text, root_node)
                        validated = model.model_validate(loaded_data)
                        output_data = validated.model_dump(mode="python")
                        _apply_values_to_component_tree(component_tree, output_data)
                        validation_label.set_text("")
                        on_field_change()
                        _trigger_render()
                        file_name = getattr(upload_event, "name", None)
                        if file_name is None:
                            file_name = getattr(
                                getattr(upload_event, "file", None),
                                "name",
                                "uploaded YAML",
                            )
                        ui.notify(
                            f"Loaded configuration from {file_name}", type="positive"
                        )
                    except Exception as ex:
                        validation_label.set_text(f"YAML load error: {ex}")
                        ui.notify(f"YAML load failed: {ex}", type="negative")
                    finally:
                        # Reset uploader state so selecting the same file again triggers upload.
                        yaml_upload.run_method("reset")

                def _pick_yaml_file():
                    yaml_upload.run_method("reset")
                    yaml_upload.run_method("pickFiles")

                with ui.row().classes("gap-2 mt-2"):
                    refresh_button = ui.button(  # noqa: F841
                        "Refresh",
                        icon="refresh",
                        on_click=lambda: _trigger_render(),
                    ).props("unelevated color=primary")
                    yaml_upload = (
                        ui.upload(
                            label="Load YAML",
                            auto_upload=True,
                            on_upload=_load_yaml_upload,
                        )
                        .props("accept=.yaml,.yml")
                        .classes("hidden")
                    )
                    ui.button(
                        "Load YAML",
                        icon="upload_file",
                        on_click=_pick_yaml_file,
                    ).props("unelevated color=primary")
                    with ui.dropdown_button(
                        "Download STL",
                        icon="download",
                        split=True,
                        auto_close=True,
                        on_click=lambda: _download_export("stl"),
                    ).props("unelevated color=secondary"):
                        ui.menu_item("Configuration", on_click=_download_yaml)
                        ui.menu_item(
                            "STL Files", on_click=lambda: _download_export("stl")
                        )
                        step_download_item = ui.menu_item(
                            "STEP Files",
                            on_click=lambda: _download_export("step"),
                        )

            # right column: viewer iframe
            with ui.column().classes("w-2/3 relative p-0"):

                # OCP viewer embedded in an iframe
                ui.element("iframe").props(
                    f'src="{embed_url}" title="OCP Viewer"'
                ).style("width:100%;height:calc(100vh - 56px);border:0;")

                # Dirty state overlay (badge removed, overlay retained).
                dirty_overlay = (
                    ui.element("div")
                    .classes(
                        "absolute inset-0 flex items-center justify-center p-6 pointer-events-none"
                    )
                    .style("background: rgba(15, 23, 42, 0.18);")
                )
                with dirty_overlay:
                    ui.label("Configuration changed - press Refresh to update").classes(
                        "text-white text-base font-semibold text-center drop-shadow px-5 py-3 max-w-md rounded-xl"
                    ).style(
                        "background: rgba(15, 23, 42, 0.34);"
                        "border: 1px solid rgba(255, 255, 255, 0.34);"
                    )

        def _sync_overlay_state():
            dirty_overlay.set_visibility(partomatic.preview_state == PreviewState.DIRTY)

        def on_field_change(_event=None):
            output_data, ok = _current_validated()
            _sync_export_visibility(output_data)
            if not ok:
                _sync_overlay_state()
                return
            partomatic._config.update_from_mapping(output_data)
            partomatic.invalidate_preview()
            _sync_overlay_state()

        for component in form_state.values():
            component.on_value_change(on_field_change)
            component.on("keydown.enter", lambda _event: _trigger_render())

        # seed YAML preview and show dirty state on first load
        on_field_change()

        def _trigger_render():
            output_data, ok = _current_validated()
            if not ok:
                return
            try:
                partomatic._config.update_from_mapping(output_data)
                partomatic.invalidate_preview()
                partomatic.compile_for_preview()
                partomatic.display(
                    viewer_host=viewer_host,
                    viewer_port=viewer_port,
                )
                _sync_overlay_state()
            except Exception as ex:
                partomatic._preview_state = PreviewState.ERROR
                partomatic._preview_error = f"Render error: {ex}"
                validation_label.set_text(partomatic._preview_error)
                _sync_overlay_state()

        # initial render on load
        ui.timer(1.5, lambda: _trigger_render(), once=True)

    ui.run(
        host=host,
        port=port,
        reload=False,
        show=False,
        root=build_ui,
        title="partomatic configurator",
    )
