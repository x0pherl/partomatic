import pytest

from partomatic import Partomatic, PartomaticConfig, PreviewState
from partomatic.partomatic_preview import PartomaticPreviewMixin


class PreviewConfig(PartomaticConfig):
    stl_folder: str = "NONE"
    should_fail: bool = False


class PreviewWidget(Partomatic):
    _config: PreviewConfig = PreviewConfig()

    def compile(self):
        if self._config.should_fail:
            raise RuntimeError("compile failed")


class TestPartomaticPreview:

    def test_preview_state_without_is_dirty_returns_internal_state(self):
        class BarePreview(PartomaticPreviewMixin):
            pass

        widget = BarePreview()
        widget._init_preview_state()
        widget._preview_state = PreviewState.CLEAN

        assert widget.preview_state == PreviewState.CLEAN

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

    def test_compile_for_preview_short_circuits_when_not_dirty(self):
        widget = PreviewWidget()
        widget.compile_for_preview()
        compile_state = widget.preview_state

        widget.compile_for_preview()

        assert compile_state == PreviewState.CLEAN
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

    def test_launch_preview_compiles_and_displays(self, monkeypatch):
        display_calls = []
        monkeypatch.setattr(
            "partomatic.partomatic_preview_app._ensure_viewer_running",
            lambda *_a, **_k: None,
        )
        import partomatic.partomatic_preview as _pm

        monkeypatch.setattr(
            _pm.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt)
        )

        widget = PreviewWidget()
        monkeypatch.setattr(widget, "compile_for_preview", lambda: None)
        widget.display = lambda **kwargs: display_calls.append(kwargs)
        widget.launch_preview(viewer_host="127.0.0.1", viewer_port=3939)

        assert display_calls[-1] == {"viewer_host": "127.0.0.1", "viewer_port": 3939}

    def test_launch_preview_prints_viewer_url(self, monkeypatch, capsys):
        monkeypatch.setattr(
            "partomatic.partomatic_preview_app._ensure_viewer_running",
            lambda *_a, **_k: None,
        )
        import partomatic.partomatic_preview as _pm

        monkeypatch.setattr(
            _pm.time, "sleep", lambda _: (_ for _ in ()).throw(KeyboardInterrupt)
        )

        widget = PreviewWidget()
        monkeypatch.setattr(widget, "compile_for_preview", lambda: None)
        widget.display = lambda **kwargs: None
        widget.launch_preview(viewer_host="127.0.0.1", viewer_port=3939)

        out = capsys.readouterr().out
        assert "127.0.0.1:3939" in out
        assert "Ctrl+C" in out
