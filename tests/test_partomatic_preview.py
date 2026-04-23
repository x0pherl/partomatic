import pytest
from types import ModuleType
import sys
from unittest.mock import patch

from partomatic import Partomatic, PartomaticConfig, PreviewState


class PreviewConfig(PartomaticConfig):
    stl_folder: str = "NONE"
    should_fail: bool = False


class PreviewWidget(Partomatic):
    _config: PreviewConfig = PreviewConfig()

    def compile(self):
        if self._config.should_fail:
            raise RuntimeError("compile failed")


class TestPartomaticPreview:
    def test_initial_preview_state(self):
        widget = PreviewWidget()
        assert widget.preview_state == PreviewState.DIRTY
        assert widget.preview_error is None

    def test_invalidate_preview_marks_dirty_and_clears_error(self):
        widget = PreviewWidget()
        widget._preview_error = "prior error"

        widget.invalidate_preview()

        assert widget.preview_state == PreviewState.DIRTY
        assert widget.preview_error is None

    def test_compile_for_preview_success_transitions(self):
        widget = PreviewWidget()
        widget.invalidate_preview()

        widget.compile_for_preview()

        assert widget.preview_state == PreviewState.CLEAN
        assert widget.preview_error is None

    def test_compile_for_preview_failure_transitions(self):
        widget = PreviewWidget(should_fail=True)

        with pytest.raises(RuntimeError, match="compile failed"):
            widget.compile_for_preview()

        assert widget.preview_state == PreviewState.ERROR
        assert widget.preview_error == "compile failed"

    def test_preview_ui_spec(self):
        widget = PreviewWidget()
        spec = widget._preview_ui_spec(viewer_host="localhost", viewer_port=4040)

        assert spec["class_name"] == "PreviewWidget"
        assert spec["viewer_url"] == "http://localhost:4040"
        assert spec["initial_state"] == "dirty"

    def test_launch_preview_missing_gui_dependency(self, monkeypatch):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "nicegui":
                raise ModuleNotFoundError("No module named 'nicegui'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)

        with pytest.raises(ModuleNotFoundError, match="partomatic\\[webui\\]"):
            PreviewWidget().launch_preview()

    def test_launch_preview_foreground_and_background(self):
        calls = []

        def fake_run_preview(**kwargs):
            calls.append(kwargs)
            return "ok"

        fake_app_module = ModuleType("partomatic.partomatic_preview_app")
        fake_app_module.run_preview = fake_run_preview
        fake_nicegui_module = ModuleType("nicegui")

        widget = PreviewWidget()
        with patch.dict(
            sys.modules,
            {
                "partomatic.partomatic_preview_app": fake_app_module,
                "nicegui": fake_nicegui_module,
            },
        ):
            result = widget.launch_preview(port=8510)
            assert result == "ok"
            assert calls[-1]["port"] == 8510
            assert calls[-1]["partomatic"] is widget

            thread = widget.launch_preview(background=True)
            thread.join(timeout=1)
            assert thread.name == "partomatic-preview-ui"
            assert calls[-1]["spec"]["class_name"] == "PreviewWidget"
