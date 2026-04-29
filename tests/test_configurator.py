"""Tests for the configurator: combined config-editor + preview window."""

import socket
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from partomatic import Partomatic, PartomaticConfig, PreviewState
from partomatic.configurator_app import find_available_port


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class ConfiguratorConfig(PartomaticConfig):
    stl_folder: str = "NONE"
    size: float = 20.0
    should_fail: bool = False


class ConfiguratorWidget(Partomatic):
    _config: ConfiguratorConfig = ConfiguratorConfig()

    def compile(self):
        if self._config.should_fail:
            raise RuntimeError("compile failed")


# ---------------------------------------------------------------------------
# Port utilities
# ---------------------------------------------------------------------------


class TestFindAvailablePort:
    def test_returns_start_port_when_free(self):
        # Find an actually free port via the OS, then confirm the helper returns it
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", 0))
            free_port = s.getsockname()[1]
        # socket is released now — find_available_port should claim it
        result = find_available_port(host="localhost", start_port=free_port, retries=0)
        assert result == free_port

    def test_increments_past_occupied_port(self):
        # occupy the start port, then confirm the helper steps to the next one
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
            occupied.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            occupied.bind(("localhost", 0))
            occupied_port = occupied.getsockname()[1]

            result = find_available_port(
                host="localhost", start_port=occupied_port, retries=10
            )
            assert result > occupied_port

    def test_raises_when_all_ports_occupied(self):
        """Patch bind to always raise OSError so exhaustion is guaranteed."""
        with patch("socket.socket") as mock_socket_cls:
            instance = MagicMock()
            instance.__enter__ = lambda s: s
            instance.__exit__ = MagicMock(return_value=False)
            instance.bind.side_effect = OSError("address in use")
            mock_socket_cls.return_value = instance

            with pytest.raises(OSError, match="No free port found"):
                find_available_port(host="localhost", start_port=9000, retries=3)


# ---------------------------------------------------------------------------
# launch_configurator on Partomatic
# ---------------------------------------------------------------------------


class TestLaunchConfigurator:
    def _make_fake_modules(self):
        calls = []

        def fake_run_configurator(**kwargs):
            calls.append(kwargs)
            return "ok"

        fake_app = ModuleType("partomatic.configurator_app")
        fake_app.run_configurator = fake_run_configurator
        fake_nicegui = ModuleType("nicegui")
        return calls, fake_app, fake_nicegui

    def test_missing_nicegui_raises(self, monkeypatch):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "nicegui":
                raise ModuleNotFoundError("No module named 'nicegui'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)

        with pytest.raises(ModuleNotFoundError, match="partomatic\\[webui\\]"):
            ConfiguratorWidget().launch_configurator()

    def test_foreground_dispatch(self):
        calls, fake_app, fake_nicegui = self._make_fake_modules()
        widget = ConfiguratorWidget()

        with patch.dict(
            sys.modules,
            {
                "partomatic.configurator_app": fake_app,
                "nicegui": fake_nicegui,
            },
        ):
            result = widget.launch_configurator(
                port=8600,
                viewer_host="127.0.0.1",
                viewer_port=3939,
            )

        assert result == "ok"
        assert len(calls) == 1
        kw = calls[0]
        assert kw["partomatic"] is widget
        assert kw["port"] == 8600
        assert "viewer_url" in kw["spec"]
        assert "config_spec" in kw["spec"]
        assert kw["spec"]["class_name"] == "ConfiguratorWidget"

    def test_background_dispatch(self):
        calls, fake_app, fake_nicegui = self._make_fake_modules()
        widget = ConfiguratorWidget()

        with patch.dict(
            sys.modules,
            {
                "partomatic.configurator_app": fake_app,
                "nicegui": fake_nicegui,
            },
        ):
            thread = widget.launch_configurator(background=True, port=8601)
            thread.join(timeout=1)

        assert thread.name == "partomatic-configurator"
        assert len(calls) == 1
        assert calls[0]["partomatic"] is widget

    def test_spec_includes_config_and_viewer(self):
        calls, fake_app, fake_nicegui = self._make_fake_modules()
        widget = ConfiguratorWidget()

        with patch.dict(
            sys.modules,
            {
                "partomatic.configurator_app": fake_app,
                "nicegui": fake_nicegui,
            },
        ):
            widget.launch_configurator(
                port=8602,
                viewer_host="10.0.0.1",
                viewer_port=4040,
            )

        spec = calls[0]["spec"]
        assert spec["viewer_url"] == "http://10.0.0.1:4040"
        config_spec = spec["config_spec"]
        assert "fields" in config_spec
        assert "size" in config_spec["fields"]


# ---------------------------------------------------------------------------
# Dirty / clean state round-trip via update_from_mapping
# ---------------------------------------------------------------------------


class TestDirtyCleanStateCycle:
    def test_config_change_marks_dirty(self):
        widget = ConfiguratorWidget()
        widget.compile_for_preview()
        assert widget.preview_state == PreviewState.CLEAN

        widget._config.update_from_mapping({"size": 21.0, "stl_folder": "NONE"})
        widget.invalidate_preview()
        assert widget.preview_state == PreviewState.DIRTY

    def test_config_update_then_compile_reaches_clean(self):
        widget = ConfiguratorWidget()
        widget._config.update_from_mapping({"size": 42.0, "stl_folder": "NONE"})
        assert widget._config.size == 42.0

        widget.invalidate_preview()
        widget.compile_for_preview()
        assert widget.preview_state == PreviewState.CLEAN

    def test_failed_compile_marks_error_and_keeps_dirty_message(self):
        widget = ConfiguratorWidget(should_fail=True)
        widget.invalidate_preview()

        with pytest.raises(RuntimeError):
            widget.compile_for_preview()

        assert widget.preview_state == PreviewState.ERROR
        assert widget.preview_error == "compile failed"

    def test_render_updates_config_and_clears_error_on_next_success(self):
        widget = ConfiguratorWidget(should_fail=True)

        with pytest.raises(RuntimeError):
            widget.compile_for_preview()

        # fix config and render again
        widget._config.update_from_mapping({"should_fail": False, "stl_folder": "NONE"})
        widget.invalidate_preview()
        widget.compile_for_preview()
        assert widget.preview_state == PreviewState.CLEAN
        assert widget.preview_error is None
