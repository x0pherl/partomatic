from types import ModuleType
import sys

import partomatic.partomatic_preview_app as preview_app


def test_viewer_embed_url_variants():
    assert (
        preview_app._viewer_embed_url("http://127.0.0.1:3939")
        == "http://127.0.0.1:3939/viewer"
    )
    assert (
        preview_app._viewer_embed_url("http://127.0.0.1:3939/")
        == "http://127.0.0.1:3939/viewer"
    )
    assert (
        preview_app._viewer_embed_url("http://127.0.0.1:3939/viewer")
        == "http://127.0.0.1:3939/viewer"
    )


def test_is_endpoint_reachable_success_and_failure(monkeypatch):
    class _Ctx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        preview_app.socket, "create_connection", lambda *_a, **_k: _Ctx()
    )
    assert preview_app._is_endpoint_reachable("localhost", 1234)

    def fail(*_a, **_k):
        raise OSError("nope")

    monkeypatch.setattr(preview_app.socket, "create_connection", fail)
    assert not preview_app._is_endpoint_reachable("localhost", 1234)


def test_start_ocp_viewer_skips_when_existing_thread_alive(monkeypatch):
    class _Alive:
        def is_alive(self):
            return True

    preview_app._viewer_threads["127.0.0.1:3939"] = _Alive()

    started = {"value": False}

    class _Thread:
        def __init__(self, **_kwargs):
            pass

        def start(self):
            started["value"] = True

    monkeypatch.setattr(preview_app.threading, "Thread", _Thread)

    preview_app._start_ocp_viewer("127.0.0.1", 3939)

    assert started["value"] is False


def test_start_ocp_viewer_starts_thread_and_registers(monkeypatch):
    preview_app._viewer_threads.clear()

    started = {"value": False}

    class _Thread:
        def __init__(self, target=None, daemon=None, name=None):
            self.target = target
            self.daemon = daemon
            self.name = name

        def start(self):
            started["value"] = True

        def is_alive(self):
            return True

    monkeypatch.setattr(preview_app.threading, "Thread", _Thread)

    preview_app._start_ocp_viewer("127.0.0.1", 3939)

    assert started["value"] is True
    key = "127.0.0.1:3939"
    assert key in preview_app._viewer_threads


def test_start_ocp_viewer_run_server_handles_system_exit(monkeypatch):
    preview_app._viewer_threads.clear()

    loop_closed = {"value": False}

    class _Loop:
        def close(self):
            loop_closed["value"] = True

    monkeypatch.setattr(preview_app.asyncio, "new_event_loop", lambda: _Loop())
    monkeypatch.setattr(preview_app.asyncio, "set_event_loop", lambda *_a, **_k: None)

    class _Viewer:
        def __init__(self, _config):
            pass

        def start(self):
            raise SystemExit()

    fake_mod = ModuleType("ocp_vscode.standalone")
    fake_mod.Viewer = _Viewer

    class _Thread:
        def __init__(self, target=None, daemon=None, name=None):
            self.target = target
            self.daemon = daemon
            self.name = name

        def start(self):
            self.target()

        def is_alive(self):
            return True

    monkeypatch.setattr(preview_app.threading, "Thread", _Thread)
    with monkeypatch.context() as m:
        m.setitem(sys.modules, "ocp_vscode.standalone", fake_mod)
        preview_app._start_ocp_viewer("127.0.0.1", 3939)

    assert loop_closed["value"]


def test_start_ocp_viewer_run_server_logs_exception(monkeypatch):
    preview_app._viewer_threads.clear()

    class _Loop:
        def close(self):
            return None

    monkeypatch.setattr(preview_app.asyncio, "new_event_loop", lambda: _Loop())
    monkeypatch.setattr(preview_app.asyncio, "set_event_loop", lambda *_a, **_k: None)

    class _Viewer:
        def __init__(self, _config):
            pass

        def start(self):
            raise RuntimeError("failed")

    fake_mod = ModuleType("ocp_vscode.standalone")
    fake_mod.Viewer = _Viewer

    logged = {"value": False}
    monkeypatch.setattr(
        preview_app._log,
        "exception",
        lambda *_a, **_k: logged.__setitem__("value", True),
    )

    class _Thread:
        def __init__(self, target=None, daemon=None, name=None):
            self.target = target
            self.daemon = daemon
            self.name = name

        def start(self):
            self.target()

        def is_alive(self):
            return True

    monkeypatch.setattr(preview_app.threading, "Thread", _Thread)
    with monkeypatch.context() as m:
        m.setitem(sys.modules, "ocp_vscode.standalone", fake_mod)
        preview_app._start_ocp_viewer("127.0.0.1", 3939)

    assert logged["value"]


def test_ensure_viewer_running_already_reachable(monkeypatch):
    called = {"start": 0}
    monkeypatch.setattr(preview_app, "_is_endpoint_reachable", lambda *_a, **_k: True)
    monkeypatch.setattr(
        preview_app,
        "_start_ocp_viewer",
        lambda *_a, **_k: called.__setitem__("start", 1),
    )

    preview_app._ensure_viewer_running("http://127.0.0.1:3939")
    assert called["start"] == 0


def test_ensure_viewer_running_waits_until_ready(monkeypatch):
    reach = iter([False, False, True])
    monkeypatch.setattr(
        preview_app, "_is_endpoint_reachable", lambda *_a, **_k: next(reach)
    )

    started = {"value": False}
    monkeypatch.setattr(
        preview_app,
        "_start_ocp_viewer",
        lambda *_a, **_k: started.__setitem__("value", True),
    )

    t = {"value": 0.0}
    monkeypatch.setattr(
        preview_app.time,
        "monotonic",
        lambda: t.__setitem__("value", t["value"] + 0.1) or t["value"],
    )
    monkeypatch.setattr(preview_app.time, "sleep", lambda *_a, **_k: None)

    preview_app._ensure_viewer_running(
        "http://127.0.0.1:3939", wait_timeout=1.0, poll_interval=0.01
    )

    assert started["value"]


def test_ensure_viewer_running_timeout_logs_warning(monkeypatch):
    monkeypatch.setattr(preview_app, "_is_endpoint_reachable", lambda *_a, **_k: False)
    monkeypatch.setattr(preview_app, "_start_ocp_viewer", lambda *_a, **_k: None)

    times = iter([0.0, 0.2, 0.4, 0.6, 2.0])
    monkeypatch.setattr(preview_app.time, "monotonic", lambda: next(times))
    monkeypatch.setattr(preview_app.time, "sleep", lambda *_a, **_k: None)

    warnings = []
    monkeypatch.setattr(
        preview_app._log,
        "warning",
        lambda *args, **kwargs: warnings.append((args, kwargs)),
    )

    preview_app._ensure_viewer_running(
        "http://127.0.0.1:3939", wait_timeout=0.5, poll_interval=0.01
    )

    assert warnings
