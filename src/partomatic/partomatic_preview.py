"""Preview-state helpers for Partomatic objects.

This module intentionally contains no UI orchestration. `compile()` remains
the source of geometry generation (usually populating `self.parts`).
"""

from enum import Enum
from threading import Thread


class PreviewState(Enum):
    CLEAN = "clean"
    DIRTY = "dirty"
    RENDERING = "rendering"
    ERROR = "error"


class PartomaticPreviewMixin:
    def _init_preview_state(self):
        self._preview_state = PreviewState.DIRTY
        self._preview_error = None

    @property
    def preview_state(self) -> PreviewState:
        return self._preview_state

    @property
    def preview_error(self) -> str | None:
        return self._preview_error

    def invalidate_preview(self):
        self._preview_state = PreviewState.DIRTY
        self._preview_error = None

    def compile_for_preview(self):
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
        return {
            "class_name": self.__class__.__name__,
            "viewer_url": f"http://{viewer_host}:{viewer_port}",
            "initial_state": self.preview_state.value,
            "initial_error": self.preview_error,
        }

    def launch_preview(
        self,
        host: str = "localhost",
        port: int = 8503,
        viewer_host: str = "127.0.0.1",
        viewer_port: int = 3939,
        background: bool = False,
    ):
        """Launch a web preview shell for this Partomatic object.

        This UI only covers preview rendering controls and viewer embedding.
        It does not include configuration editing orchestration.
        """
        try:
            import nicegui  # noqa: F401
        except ModuleNotFoundError as ex:
            raise ModuleNotFoundError(
                "Missing optional GUI dependencies. Install with: pip install partomatic[webui]"
            ) from ex

        from .partomatic_preview_app import run_preview

        spec = self._preview_ui_spec(
            viewer_host=viewer_host,
            viewer_port=viewer_port,
        )

        if background:
            thread = Thread(
                target=run_preview,
                kwargs={
                    "partomatic": self,
                    "spec": spec,
                    "host": host,
                    "port": port,
                },
                daemon=True,
                name="partomatic-preview-ui",
            )
            thread.start()
            return thread

        return run_preview(
            partomatic=self,
            spec=spec,
            host=host,
            port=port,
        )
