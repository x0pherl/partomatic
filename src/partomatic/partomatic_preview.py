"""Preview-state and launch helpers for Partomatic objects.

`compile()` remains the source of geometry generation (usually populating
`self.parts`).
"""

import time
from enum import Enum
from threading import Thread


class PreviewState(Enum):
    """Preview lifecycle state for rendered geometry."""

    CLEAN = "clean"
    DIRTY = "dirty"
    RENDERING = "rendering"
    ERROR = "error"


class PartomaticPreviewMixin:
    """Preview state and launcher helpers for Partomatic classes."""

    def _init_preview_state(self):
        """Initialize preview state fields on the instance."""
        self._preview_state = PreviewState.DIRTY
        self._preview_error = None

    @property
    def preview_state(self) -> PreviewState:
        """Return computed preview state using dirty-tracking when available."""
        if self._preview_state in (PreviewState.RENDERING, PreviewState.ERROR):
            return self._preview_state
        if hasattr(self, "is_dirty"):
            return PreviewState.DIRTY if self.is_dirty else PreviewState.CLEAN
        return self._preview_state

    @property
    def preview_error(self) -> str | None:
        """Return the last preview error message, if any."""
        return self._preview_error

    def invalidate_preview(self):
        """Clear preview errors and mark stale state as dirty."""
        if self._preview_state == PreviewState.ERROR:
            self._preview_state = PreviewState.DIRTY
        self._preview_error = None

    def compile_for_preview(self):
        """Compile the model and update preview state transitions."""
        if hasattr(self, "is_dirty") and not self.is_dirty:
            self._preview_state = PreviewState.CLEAN
            self._preview_error = None
            return
        self._preview_state = PreviewState.RENDERING
        self._preview_error = None
        try:
            self.compile()
        except Exception as ex:
            self._preview_state = PreviewState.ERROR
            self._preview_error = str(ex)
            raise
        self._preview_state = PreviewState.CLEAN

    def _preview_ui_spec(
        self,
        viewer_host: str = "127.0.0.1",
        viewer_port: int = 3939,
    ) -> dict:
        """Build lightweight preview metadata for UI launchers."""
        return {
            "class_name": self.__class__.__name__,
            "viewer_url": f"http://{viewer_host}:{viewer_port}",
            "initial_state": self.preview_state.value,
            "initial_error": self.preview_error,
        }

    def launch_preview(
        self,
        viewer_host: str = "127.0.0.1",
        viewer_port: int = 3939,
    ):
        """Compile this part and display it in the OCP viewer.

        Starts the standalone OCP viewer if it is not already running, then
        compiles the part and pushes it to the viewer. This call blocks until
        interrupted with Ctrl+C.

        Args:
            viewer_host: OCP viewer standalone host.
            viewer_port: OCP viewer standalone port.
        """
        from .partomatic_preview_app import _ensure_viewer_running

        viewer_url = f"http://{viewer_host}:{viewer_port}"
        _ensure_viewer_running(viewer_url)
        self.compile_for_preview()
        self.display(viewer_host=viewer_host, viewer_port=viewer_port)
        print(f"OCP viewer running at {viewer_url}/viewer")
        print("Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping preview.")

    def launch_configurator(
        self,
        host: str = "localhost",
        port: int = 8505,
        port_retries: int = 10,
        viewer_host: str = "127.0.0.1",
        viewer_port: int = 3939,
        background: bool = False,
    ):
        """Launch a combined configurator window: config form + 3D preview in one page.

        When any configuration field changes the preview is marked DIRTY and an overlay
        is shown on the viewer until the "Refresh" button is clicked.

        Args:
            host: NiceGUI server host.
            port: Starting port; incremented up to port_retries times if occupied.
            port_retries: Number of additional ports to try after start_port.
            viewer_host: OCP viewer standalone host.
            viewer_port: OCP viewer standalone port.
            background: When True run the UI server in a daemon thread.
        """
        try:
            import nicegui  # noqa: F401
        except ModuleNotFoundError as ex:
            raise ModuleNotFoundError(
                "Missing optional GUI dependencies. Install with: pip install partomatic[webui]"
            ) from ex

        from .configurator_app import run_configurator

        preview_spec = self._preview_ui_spec(
            viewer_host=viewer_host,
            viewer_port=viewer_port,
        )
        config_spec = self._config._editor_spec()

        spec = {
            "class_name": self.__class__.__name__,
            "viewer_url": preview_spec["viewer_url"],
            "config_spec": config_spec,
        }

        kwargs = dict(
            partomatic=self,
            spec=spec,
            host=host,
            port=port,
            port_retries=port_retries,
        )

        if background:
            thread = Thread(
                target=run_configurator,
                kwargs=kwargs,
                daemon=True,
                name="partomatic-configurator",
            )
            thread.start()
            return thread

        return run_configurator(**kwargs)
