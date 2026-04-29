import runpy
import asyncio
import io
from pathlib import Path
from types import SimpleNamespace
import pytest

import partomatic.configurator_app as configurator_app
from partomatic import PreviewState


class _FakeElement:
    def __init__(self, value=None):
        self.value = value
        self.text = ""
        self.visible = True
        self._on_click = None
        self._on_value_change = None
        self._events = {}
        self.run_method_calls = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def classes(self, _value):
        return self

    def props(self, _value):
        return self

    def style(self, _value):
        return self

    def set_text(self, value):
        self.text = value

    def set_visibility(self, value):
        self.visible = value

    def on_value_change(self, callback):
        self._on_value_change = callback
        return self

    def on(self, event_name, callback):
        self._events[event_name] = callback
        return self

    def run_method(self, _name, *_args, **_kwargs):
        self.run_method_calls.append(_name)
        return None


class _FakeUI:
    def __init__(self):
        self.buttons = []
        self.badges = []
        self.uploads = []
        self.menu_items = []
        self.downloads = []
        self.last_notify = None
        self.last_run = None
        self.last_title = None

    def page_title(self, value):
        self.last_title = value

    def row(self):
        return _FakeElement()

    def column(self):
        return _FakeElement()

    def card(self):
        return _FakeElement()

    def label(self, *_args, **_kwargs):
        return _FakeElement()

    def badge(self, *_args, **_kwargs):
        element = _FakeElement()
        if _args:
            element.text = _args[0]
        self.badges.append(element)
        return element

    def textarea(self, *_args, **_kwargs):
        return _FakeElement(value="")

    def button(self, _label, on_click=None, **_kwargs):
        element = _FakeElement()
        element.text = _label
        element._on_click = on_click
        self.buttons.append(element)
        return element

    def dropdown_button(self, label, **_kwargs):
        element = _FakeElement()
        element.text = label
        element._on_click = _kwargs.get("on_click")
        self.buttons.append(element)
        return element

    def menu_item(self, label, on_click=None, **_kwargs):
        element = _FakeElement()
        element.text = label
        element._on_click = on_click
        self.menu_items.append(element)
        return element

    def upload(self, label=None, on_upload=None, **_kwargs):
        element = _FakeElement()
        element.text = label or ""
        element._on_upload = on_upload
        self.uploads.append(element)
        return element

    def element(self, *_args, **_kwargs):
        return _FakeElement()

    def timer(self, _interval, callback, once=False):
        if once:
            callback()

    def notify(self, message, type=None):
        self.last_notify = (message, type)

    def download(self, src, filename=None, media_type=""):
        self.downloads.append((src, filename, media_type))

    def run(self, **kwargs):
        self.last_run = kwargs
        kwargs["root"]()


class _Validated:
    def __init__(self, data):
        self._data = data

    def model_dump(self, mode="python"):
        _ = mode
        return self._data


class _Model:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail

    def model_validate(self, value):
        if self.should_fail:
            from pydantic import ValidationError

            raise ValidationError.from_exception_data(
                "Cfg",
                [
                    {
                        "type": "value_error",
                        "loc": ("x",),
                        "msg": "bad",
                        "input": value,
                        "ctx": {"error": "bad"},
                    }
                ],
            )
        return _Validated(value)


class _Config:
    def __init__(self):
        self.updated_with = None
        self.enable_step_exports = False
        self.size = 20
        self.value = 7

    def update_from_mapping(self, value):
        self.updated_with = value
        for key, item in value.items():
            setattr(self, key, item)

    def as_dict(self):
        return {
            key: value for key, value in self.__dict__.items() if key != "updated_with"
        }


class _Partomatic:
    def __init__(self, fail_display=False):
        self._config = _Config()
        self.fail_display = fail_display
        self.invalidate_called = 0
        self.compile_called = 0
        self.display_calls = []
        self._compiled_config_snapshot = None
        self._preview_state = PreviewState.DIRTY
        self._preview_error = None

    @property
    def is_dirty(self):
        if self._compiled_config_snapshot is None:
            return True
        return self._config.as_dict() != self._compiled_config_snapshot

    @property
    def preview_state(self):
        if self._preview_state in (PreviewState.RENDERING, PreviewState.ERROR):
            return self._preview_state
        return PreviewState.DIRTY if self.is_dirty else PreviewState.CLEAN

    @property
    def preview_error(self):
        return self._preview_error

    def invalidate_preview(self):
        self.invalidate_called += 1
        if self._preview_state == PreviewState.ERROR:
            self._preview_state = PreviewState.DIRTY
        self._preview_error = None

    def compile_for_preview(self):
        if not self.is_dirty:
            self._preview_state = PreviewState.CLEAN
            self._preview_error = None
            return
        self._preview_state = PreviewState.RENDERING
        self._preview_error = None
        self.compile()
        self._preview_state = PreviewState.CLEAN

    def compile(self):
        self.compile_called += 1
        self._compiled_config_snapshot = dict(self._config.as_dict())

    def display(self, **kwargs):
        if self.fail_display:
            raise RuntimeError("display failed")
        self.display_calls.append(kwargs)

    def export_stls_to_directory(self, output_dir):
        output_path = Path(output_dir)
        first = output_path / "part-a.stl"
        second = output_path / "part-b.stl"
        first.write_bytes(b"stl-a")
        second.write_bytes(b"stl-b")
        return [first, second]

    def export_steps_to_directory(self, output_dir):
        output_path = Path(output_dir)
        step_path = output_path / "part.step"
        step_path.write_bytes(b"step")
        return [step_path]


class _Component:
    def __init__(self, value):
        self.value = value
        self.callback = None
        self.events = {}

    def on_value_change(self, callback):
        self.callback = callback
        return self

    def on(self, event_name, callback):
        self.events[event_name] = callback
        return self


class _UploadedFile:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._data = data

    async def text(self, encoding: str = "utf-8"):
        return self._data.decode(encoding)


def _invoke_maybe_async(callback, *args, **kwargs):
    result = callback(*args, **kwargs)
    if asyncio.iscoroutine(result):
        return asyncio.run(result)
    return result


def _collect_with_form_state(component):
    def _collector(_fields_spec, form_state):
        form_state["value"] = component
        form_state["size"] = component
        return {"value": component, "size": component}

    return _collector


def _collect_with_named_form_state(component, key_name):
    def _collector(_fields_spec, form_state):
        form_state[key_name] = component
        if key_name != "value":
            form_state["value"] = component
            return {key_name: component, "value": component}
        return {key_name: component}

    return _collector


def test_module_main_guard_adjusts_path_and_runs(monkeypatch):
    script = str(Path(__file__).parents[1] / "src/partomatic/configurator_app.py")
    src_root = str(Path(script).resolve().parents[1])
    script_dir = str(Path(script).resolve().parent)

    import sys
    import os

    pruned_sys_path = [p for p in sys.path if os.path.abspath(p) != src_root] + [
        script_dir
    ]
    monkeypatch.setattr(sys, "path", pruned_sys_path)

    runpy.run_path(script, run_name="__main__")

    assert sys.path[0] == src_root


def test_extract_uploaded_text_supports_sync_text_and_content_paths():
    event_text = SimpleNamespace(
        file=SimpleNamespace(text=lambda _enc: "a: 1\n"),
    )
    assert asyncio.run(configurator_app._extract_uploaded_text(event_text)) == "a: 1\n"

    event_bytes = SimpleNamespace(content=io.BytesIO(b"b: 2\n"))
    assert asyncio.run(configurator_app._extract_uploaded_text(event_bytes)) == "b: 2\n"


def test_extract_uploaded_text_supports_file_read_and_plain_string_content():
    event_file_bytes = SimpleNamespace(
        file=SimpleNamespace(read=lambda: b"c: 3\n"),
    )
    assert (
        asyncio.run(configurator_app._extract_uploaded_text(event_file_bytes))
        == "c: 3\n"
    )

    event_file_str = SimpleNamespace(
        file=SimpleNamespace(read=lambda: "d: 4\n"),
    )
    assert (
        asyncio.run(configurator_app._extract_uploaded_text(event_file_str)) == "d: 4\n"
    )

    event_plain_content = SimpleNamespace(content="e: 5\n")
    assert (
        asyncio.run(configurator_app._extract_uploaded_text(event_plain_content))
        == "e: 5\n"
    )


def test_extract_uploaded_text_rejects_missing_or_non_text_content():
    with pytest.raises(ValueError, match="missing"):
        asyncio.run(configurator_app._extract_uploaded_text(SimpleNamespace()))

    with pytest.raises(ValueError, match="must be text YAML"):
        asyncio.run(
            configurator_app._extract_uploaded_text(
                SimpleNamespace(content=SimpleNamespace(read=lambda: 123))
            )
        )


def test_yaml_to_config_data_error_branches_and_apply_values_skip_unknown():
    with pytest.raises(ValueError, match="empty"):
        configurator_app._yaml_to_config_data("", "cfg")

    with pytest.raises(ValueError, match="must be a mapping"):
        configurator_app._yaml_to_config_data("cfg: 7", "cfg")

    tree = {
        "size": _Component(1),
        "nested": {"x": _Component(2)},
    }
    configurator_app._apply_values_to_component_tree(
        tree,
        {"size": 9, "nested": {"x": 11}, "unknown": 17},
    )
    assert tree["size"].value == 9
    assert tree["nested"]["x"].value == 11


def test_download_payload_from_paths_raises_when_empty():
    with pytest.raises(ValueError, match="No files"):
        configurator_app._download_payload_from_paths([], "files.zip", "model/stl")


def test_run_configurator_early_returns_when_invalid(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8612)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )

    component = _Component(7)
    monkeypatch.setattr(
        configurator_app, "_collect_components", _collect_with_form_state(component)
    )
    monkeypatch.setattr(
        configurator_app,
        "_component_value",
        lambda tree: {"value": tree["value"].value},
    )
    monkeypatch.setattr(
        configurator_app,
        "_to_yaml_document",
        lambda root, data: f"{root}: {data['value']}\n",
    )

    class _AlwaysInvalidModel:
        def model_validate(self, value):
            from pydantic import ValidationError

            raise ValidationError.from_exception_data(
                "Cfg",
                [
                    {
                        "type": "value_error",
                        "loc": ("value",),
                        "msg": "bad",
                        "input": value,
                        "ctx": {"error": "bad"},
                    }
                ],
            )

    monkeypatch.setattr(
        configurator_app, "_build_model", lambda *_a, **_k: _AlwaysInvalidModel()
    )

    part = _Partomatic(fail_display=False)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {"value": {"kind": "int", "value": 7}},
        },
    }

    configurator_app.run_configurator(part, spec)

    for button in fake_ui.buttons:
        if button._on_click:
            button._on_click()

    assert part._config.updated_with is None


def test_run_configurator_revert_to_rendered_value_marks_clean(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8613)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )

    component = _Component(20)
    monkeypatch.setattr(
        configurator_app,
        "_collect_components",
        _collect_with_named_form_state(component, "size"),
    )
    monkeypatch.setattr(
        configurator_app,
        "_component_value",
        lambda tree: {"size": tree["size"].value},
    )
    monkeypatch.setattr(
        configurator_app,
        "_to_yaml_document",
        lambda root, data: f"{root}: {data['size']}\n",
    )
    monkeypatch.setattr(configurator_app, "_build_model", lambda *_a, **_k: _Model())

    part = _Partomatic(fail_display=False)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {"size": {"kind": "float", "value": 20}},
        },
    }

    configurator_app.run_configurator(part, spec)

    # Initial timer-driven render should have marked preview state clean.
    assert part.preview_state == PreviewState.CLEAN

    # Change value from rendered baseline -> DIRTY.
    component.value = 2
    component.callback(None)
    assert part.preview_state == PreviewState.DIRTY

    # Revert to the rendered baseline -> CLEAN.
    component.value = 20
    component.callback(None)
    assert part.preview_state == PreviewState.CLEAN


def test_run_configurator_enter_key_triggers_rerender(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8614)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )
    monkeypatch.setattr(configurator_app, "_build_model", lambda *_a, **_k: _Model())

    component = _Component(20)
    monkeypatch.setattr(
        configurator_app,
        "_collect_components",
        _collect_with_named_form_state(component, "size"),
    )
    monkeypatch.setattr(
        configurator_app,
        "_component_value",
        lambda tree: {"size": tree["size"].value},
    )
    monkeypatch.setattr(
        configurator_app,
        "_to_yaml_document",
        lambda root, data: f"{root}: {data['size']}\n",
    )

    part = _Partomatic(fail_display=False)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {"size": {"kind": "float", "value": 20}},
        },
    }

    configurator_app.run_configurator(part, spec)

    component.value = 31
    component.events["keydown.enter"](None)

    assert part._config.updated_with == {"size": 31}
    assert part.compile_called >= 2
    assert part.preview_state == PreviewState.CLEAN


def test_run_configurator_export_menu_downloads_yaml_and_zipped_stls(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8615)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )
    monkeypatch.setattr(configurator_app, "_build_model", lambda *_a, **_k: _Model())

    component = _Component(20)
    monkeypatch.setattr(
        configurator_app,
        "_collect_components",
        _collect_with_named_form_state(component, "size"),
    )
    monkeypatch.setattr(
        configurator_app,
        "_component_value",
        lambda tree: {"size": tree["size"].value, "enable_step_exports": False},
    )
    monkeypatch.setattr(
        configurator_app,
        "_to_yaml_document",
        lambda root, data: f"{root}: {data['size']}\n",
    )

    part = _Partomatic(fail_display=False)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {
                "size": {"kind": "float", "value": 20},
                "enable_step_exports": {"kind": "bool", "value": False},
            },
        },
    }

    configurator_app.run_configurator(part, spec)

    assert any(button.text == "Download STL" for button in fake_ui.buttons)

    yaml_item = next(
        item for item in fake_ui.menu_items if item.text == "Configuration"
    )
    stl_item = next(item for item in fake_ui.menu_items if item.text == "STL Files")
    step_item = next(item for item in fake_ui.menu_items if item.text == "STEP Files")

    assert step_item.visible is False

    yaml_item._on_click()
    assert fake_ui.downloads[-1][1] == "cfg.yaml"

    stl_item._on_click()
    assert part._config.updated_with == {"size": 20, "enable_step_exports": False}
    assert fake_ui.downloads[-1][1] == "cfg-stls.zip"
    assert fake_ui.downloads[-1][2] == "application/zip"
    assert part.display_calls, "display() should be called on download"
    assert part.preview_state == PreviewState.CLEAN


def test_run_configurator_export_compiles_when_dirty(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8620)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )
    monkeypatch.setattr(configurator_app, "_build_model", lambda *_a, **_k: _Model())

    component = _Component(20)
    monkeypatch.setattr(
        configurator_app,
        "_collect_components",
        _collect_with_named_form_state(component, "size"),
    )
    monkeypatch.setattr(
        configurator_app,
        "_component_value",
        lambda tree: {"size": tree["size"].value, "enable_step_exports": False},
    )
    monkeypatch.setattr(
        configurator_app,
        "_to_yaml_document",
        lambda root, data: f"{root}: {data['size']}\n",
    )

    part = _Partomatic(fail_display=False)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {
                "size": {"kind": "float", "value": 20},
                "enable_step_exports": {"kind": "bool", "value": False},
            },
        },
    }

    configurator_app.run_configurator(part, spec)
    part._compiled_config_snapshot = None
    before = part.compile_called

    stl_item = next(item for item in fake_ui.menu_items if item.text == "STL Files")
    stl_item._on_click()

    assert part.compile_called > before


def test_run_configurator_download_yaml_returns_early_when_invalid(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8621)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )

    class _AlwaysInvalidModel:
        def model_validate(self, value):
            from pydantic import ValidationError

            raise ValidationError.from_exception_data(
                "Cfg",
                [
                    {
                        "type": "value_error",
                        "loc": ("value",),
                        "msg": "bad",
                        "input": value,
                        "ctx": {"error": "bad"},
                    }
                ],
            )

    monkeypatch.setattr(
        configurator_app, "_build_model", lambda *_a, **_k: _AlwaysInvalidModel()
    )

    component = _Component(7)
    monkeypatch.setattr(
        configurator_app, "_collect_components", _collect_with_form_state(component)
    )

    part = _Partomatic(fail_display=False)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {"value": {"kind": "int", "value": 7}},
        },
    }

    configurator_app.run_configurator(part, spec)
    yaml_item = next(
        item for item in fake_ui.menu_items if item.text == "Configuration"
    )
    yaml_item._on_click()

    assert fake_ui.downloads == []


def test_run_configurator_export_error_sets_message_and_notifies(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8622)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )
    monkeypatch.setattr(configurator_app, "_build_model", lambda *_a, **_k: _Model())

    component = _Component(20)
    monkeypatch.setattr(
        configurator_app,
        "_collect_components",
        _collect_with_named_form_state(component, "size"),
    )
    monkeypatch.setattr(
        configurator_app,
        "_component_value",
        lambda tree: {"size": tree["size"].value, "enable_step_exports": False},
    )

    part = _Partomatic(fail_display=True)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {
                "size": {"kind": "float", "value": 20},
                "enable_step_exports": {"kind": "bool", "value": False},
            },
        },
    }

    configurator_app.run_configurator(part, spec)
    stl_item = next(item for item in fake_ui.menu_items if item.text == "STL Files")
    stl_item._on_click()

    assert fake_ui.last_notify is not None
    assert fake_ui.last_notify[1] == "negative"


def test_run_configurator_render_error_sets_preview_error(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8623)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )
    monkeypatch.setattr(configurator_app, "_build_model", lambda *_a, **_k: _Model())

    component = _Component(20)
    monkeypatch.setattr(
        configurator_app,
        "_collect_components",
        _collect_with_named_form_state(component, "size"),
    )
    monkeypatch.setattr(
        configurator_app,
        "_component_value",
        lambda tree: {"size": tree["size"].value},
    )

    part = _Partomatic(fail_display=True)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {"size": {"kind": "float", "value": 20}},
        },
    }

    configurator_app.run_configurator(part, spec)

    assert part._preview_state == PreviewState.ERROR
    assert part._preview_error.startswith("Render error:")


def test_run_configurator_step_download_visibility_and_single_file_download(
    monkeypatch,
):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8616)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )
    monkeypatch.setattr(configurator_app, "_build_model", lambda *_a, **_k: _Model())

    component = _Component(20)
    monkeypatch.setattr(
        configurator_app,
        "_collect_components",
        _collect_with_named_form_state(component, "size"),
    )
    monkeypatch.setattr(
        configurator_app,
        "_component_value",
        lambda tree: {"size": tree["value"].value, "enable_step_exports": True},
    )
    monkeypatch.setattr(
        configurator_app,
        "_to_yaml_document",
        lambda root, data: f"{root}: {data['size']}\n",
    )

    part = _Partomatic(fail_display=False)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {
                "size": {"kind": "float", "value": 20},
                "enable_step_exports": {"kind": "bool", "value": True},
            },
        },
    }

    configurator_app.run_configurator(part, spec)

    step_item = next(item for item in fake_ui.menu_items if item.text == "STEP Files")
    assert step_item.visible is True

    step_item._on_click()
    assert part._config.updated_with == {"size": 20, "enable_step_exports": True}
    assert fake_ui.downloads[-1][1] == "part.step"
    assert fake_ui.downloads[-1][2] == "model/step"


def test_run_configurator_load_yaml_upload_updates_form(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8618)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )
    monkeypatch.setattr(configurator_app, "_build_model", lambda *_a, **_k: _Model())

    component = _Component(20)
    monkeypatch.setattr(
        configurator_app, "_collect_components", _collect_with_form_state(component)
    )
    monkeypatch.setattr(
        configurator_app,
        "_component_value",
        lambda tree: {"size": tree["size"].value},
    )
    monkeypatch.setattr(
        configurator_app,
        "_to_yaml_document",
        lambda root, data: f"{root}: {data['size']}\n",
    )

    part = _Partomatic(fail_display=False)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {"size": {"kind": "float", "value": 20}},
        },
    }

    configurator_app.run_configurator(part, spec)

    upload = next(upload for upload in fake_ui.uploads if upload.text == "Load YAML")
    upload_event = SimpleNamespace(
        file=_UploadedFile("input.yaml", b"cfg:\n  size: 31\n")
    )
    _invoke_maybe_async(upload._on_upload, upload_event)

    second_upload_event = SimpleNamespace(
        file=_UploadedFile("input.yaml", b"cfg:\n  size: 33\n")
    )
    _invoke_maybe_async(upload._on_upload, second_upload_event)

    assert component.value == 33
    assert part._config.updated_with == {"size": 33}
    assert part.compile_called >= 3
    assert part.display_calls[-1] == {"viewer_host": "127.0.0.1", "viewer_port": 3939}
    assert fake_ui.last_notify == ("Loaded configuration from input.yaml", "positive")
    assert upload.run_method_calls.count("reset") >= 2


def test_run_configurator_load_yaml_upload_handles_invalid_yaml(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(configurator_app, "ui", fake_ui)
    monkeypatch.setattr(
        configurator_app, "_ensure_viewer_running", lambda *_a, **_k: None
    )
    monkeypatch.setattr(configurator_app, "find_available_port", lambda **_k: 8619)
    monkeypatch.setattr(
        configurator_app, "_viewer_embed_url", lambda _u: "http://127.0.0.1:3939/viewer"
    )
    monkeypatch.setattr(configurator_app, "_build_model", lambda *_a, **_k: _Model())

    component = _Component(20)
    monkeypatch.setattr(
        configurator_app,
        "_collect_components",
        _collect_with_named_form_state(component, "size"),
    )
    monkeypatch.setattr(
        configurator_app,
        "_component_value",
        lambda tree: {"size": tree["size"].value},
    )
    monkeypatch.setattr(
        configurator_app,
        "_to_yaml_document",
        lambda root, data: f"{root}: {data['size']}\n",
    )

    part = _Partomatic(fail_display=False)
    spec = {
        "class_name": "Widget",
        "viewer_url": "http://127.0.0.1:3939",
        "config_spec": {
            "root_node": "cfg",
            "fields": {"size": {"kind": "float", "value": 20}},
        },
    }

    configurator_app.run_configurator(part, spec)

    upload = next(upload for upload in fake_ui.uploads if upload.text == "Load YAML")
    upload_event = SimpleNamespace(file=_UploadedFile("bad.yaml", b"- not-a-mapping\n"))
    _invoke_maybe_async(upload._on_upload, upload_event)

    assert component.value == 20
    assert fake_ui.last_notify is not None
    assert fake_ui.last_notify[1] == "negative"
