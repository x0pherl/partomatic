__package__ = "partomatic"

if __name__ == "__main__":
    import os, sys

    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_root = os.path.dirname(script_dir)
    # Remove the script directory so 'partomatic' resolves to the package, not this file
    if script_dir in sys.path:
        sys.path.remove(script_dir)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

"""Part automation utilities: compile, preview, and export workflows."""

from dataclasses import field
from abc import ABC, abstractmethod
from copy import deepcopy
from functools import wraps
import inspect
from pathlib import Path
from typing import Optional

from build123d import Location, export_step, export_stl

import ocp_vscode

import logging

from partomatic.partomatic_config import PartomaticConfig
from partomatic.automatable_part import AutomatablePart
from partomatic.partomatic_preview import PartomaticPreviewMixin


class Partomatic(PartomaticPreviewMixin, ABC):
    """Base class for automatable CAD parts.

    Subclasses provide `compile()` to populate `self.parts`, while this class
    supplies display, export, configuration-loading, and preview/configurator
    launch helpers.
    """

    _config: PartomaticConfig
    parts: list[AutomatablePart] = field(default_factory=list)

    @abstractmethod
    def compile(self):
        """Build the part geometry and populate `self.parts`."""

    def display(
        self,
        viewer_host: Optional[str] = None,
        viewer_port: Optional[int] = None,
    ):
        """Show current parts in the OCP CAD viewer.

        If `viewer_port` is provided, the standalone endpoint is configured
        via `ocp_vscode.set_port(...)`. Otherwise display uses ocp_vscode's
        default integration behavior.

        Args:
            viewer_host: Hostname used with `viewer_port` for standalone viewer.
            viewer_port: Standalone viewer port to target.
        """
        # Only set port if we're explicitly told to and it's configured
        if viewer_port is not None:
            ocp_vscode.set_port(viewer_port, host=viewer_host or "127.0.0.1")

        # Clear the viewer before showing new parts to avoid accumulation
        ocp_vscode.show_clear()

        # Display without port parameter to use VS Code integration when available
        # Create deep copies of parts before moving to avoid mutating stored parts
        display_parts = [
            deepcopy(part.part).move(part.display_location) for part in self.parts
        ]
        ocp_vscode.show(display_parts)

    def complete_stl_file_path(self, part: AutomatablePart) -> str:
        """Return the final STL file path for a part.

        Args:
            part: Part metadata used to derive export path components.

        Returns:
            Absolute or source-relative resolved STL path as a string.
        """
        return str(self._complete_export_file_path(part, ".stl"))

    def complete_step_file_path(self, part: AutomatablePart) -> str:
        """Return the final STEP file path for a part.

        Args:
            part: Part metadata used to derive export path components.

        Returns:
            Absolute or source-relative resolved STEP path as a string.
        """
        return str(self._complete_export_file_path(part, ".step"))

    def _complete_export_file_path(
        self,
        part: AutomatablePart,
        suffix: str,
        output_dir: Optional[str | Path] = None,
    ) -> Path:
        """Build the export path for a part and file suffix.

        Args:
            part: Part metadata containing base file name and default folder.
            suffix: File suffix such as `.stl` or `.step`.
            output_dir: Optional override directory for exports.

        Returns:
            Resolved filesystem path for the target export file.
        """
        export_root = (
            Path(output_dir) if output_dir is not None else Path(part.stl_folder)
        )
        if not export_root.is_absolute():
            export_root = self._source_dir / export_root
        return (
            export_root
            / f"{self._config.file_prefix}{part.file_name_base}{self._config.file_suffix}"
        ).with_suffix(suffix)

    def _export_parts(
        self,
        suffix: str,
        exporter,
        output_dir: Optional[str | Path] = None,
    ) -> list[Path]:
        """Export all compiled parts with a common suffix.

        Args:
            suffix: Output file suffix for each exported part.
            exporter: Callable that writes one part to one file path.
            output_dir: Optional override directory for exports.

        Returns:
            Paths written by the exporter, in part order.

        Raises:
            FileNotFoundError: If the export directory cannot be created/found.
        """
        if output_dir is None and self._config.stl_folder == "NONE":
            logging.getLogger("partomatic").warning(
                "stl_folder is set to NONE, skipping export"
            )
            return []

        exported_paths = []
        for part in self.parts:
            export_path = self._complete_export_file_path(part, suffix, output_dir)
            if not export_path.parent.exists():
                export_path.parent.mkdir(
                    parents=True,
                    exist_ok=self._config.create_folders_if_missing,
                )
            if not export_path.parent.exists() or not export_path.parent.is_dir():
                error_str = f"Directory {export_path.parent} does not exist."
                logging.getLogger("partomatic").warning(error_str)
                raise FileNotFoundError(error_str)
            exporter(part.part, str(export_path))
            exported_paths.append(export_path)
        return exported_paths

    def export_stls(self):
        """Generate STL exports in the configured output folder."""
        return self._export_parts(".stl", export_stl)

    def export_steps(self):
        """Generate STEP exports in the configured output folder."""
        return self._export_parts(".step", export_step)

    def export_stls_to_directory(self, output_dir: str | Path):
        """Generate STL exports into a specific directory."""
        return self._export_parts(".stl", export_stl, output_dir=output_dir)

    def export_steps_to_directory(self, output_dir: str | Path):
        """Generate STEP exports into a specific directory."""
        return self._export_parts(".step", export_step, output_dir=output_dir)

    def _config_snapshot(self) -> dict:
        """Return a deep-copied snapshot of current config values."""
        return deepcopy(self._config.as_dict())

    def _mark_compiled(self):
        """Store the current config snapshot as the compiled baseline."""
        self._compiled_config_snapshot = self._config_snapshot()

    def _wrap_compile_method(self):
        """Wrap `compile` once so successful compiles update dirty state."""
        if getattr(self, "_compile_is_wrapped", False):
            return

        original_compile = self.compile

        @wraps(original_compile)
        def wrapped_compile(*args, **kwargs):
            result = original_compile(*args, **kwargs)
            self._mark_compiled()
            return result

        self.compile = wrapped_compile
        self._compile_is_wrapped = True

    @property
    def is_dirty(self) -> bool:
        """Whether config has changed since the last successful compile."""
        if self._compiled_config_snapshot is None:
            return True
        return self._config_snapshot() != self._compiled_config_snapshot

    def load_config(self, configuration: any, **kwargs):
        """Load configuration into this Partomatic instance.

        Args:
            configuration: Configuration source forwarded to
                `self._config.load_config(...)` (commonly a file path, YAML
                string, compatible config object, or `None`).
            **kwargs: Field overrides applied by the configuration loader.
        """

        logging.getLogger("partomatic").debug(
            f"loading {configuration} with kwargs: {kwargs}"
        )
        self._config.load_config(configuration, **kwargs)

    def __init__(self, configuration: any = None, **kwargs):
        """Initialize part state and load configuration.

        Args:
            configuration: Optional configuration source passed to `load_config`.
            **kwargs: Field overrides passed to `load_config`.
        """
        self.parts = []
        # we have to call self.__class__.config so it can handle instanting
        # the descendant class of PartomaticConfig instead of using the generic
        # parent implementation
        self._config = self.__class__._config
        self._source_dir = Path(inspect.getfile(self.__class__)).parent
        self._compiled_config_snapshot = None
        self._compile_is_wrapped = False
        self._wrap_compile_method()
        self._init_preview_state()
        self.load_config(configuration, **kwargs)

    def partomate(self, export_steps: bool = False):
        """Compile this part and export output files.

        Args:
            export_steps: When True, also export STEP files.

        Notes:
            Override `export_stls()` and/or `export_steps()` if a subclass wants
            custom export behavior or to disable a format.
        """
        self.compile()
        self.export_stls()
        if export_steps:
            self.export_steps()


if __name__ == "__main__":
    from build123d import BuildPart, Box, Sphere, Mode

    class DemoConfig(PartomaticConfig):
        stl_folder: str = "NONE"
        size: float = 20.0
        sphere_ratio: float = field(
            default=0.6,
            metadata={
                "kind": "float",
                "constraints": {"ge": 0.1, "le": 0.86},
                "step": 0.01,
            },
        )

    class DemoPart(Partomatic):
        _config: DemoConfig = DemoConfig()

        def compile(self):
            self.parts.clear()
            with BuildPart() as cube:
                Box(
                    self._config.size,
                    self._config.size,
                    self._config.size,
                )
                Sphere(
                    self._config.size * self._config.sphere_ratio, mode=Mode.SUBTRACT
                )
            with BuildPart() as ball:
                Box(
                    self._config.size,
                    self._config.size,
                    self._config.size,
                )
                Sphere(
                    self._config.size * self._config.sphere_ratio, mode=Mode.INTERSECT
                )
            cube.part.label = "cube"
            ball.part.label = "ball"
            self.parts.append(
                AutomatablePart(
                    cube.part,
                    "demo-cube",
                    display_location=Location(
                        (self._config.size / 2 + self._config.size / 4, 0, 0)
                    ),
                    stl_folder=self._config.stl_folder,
                )
            )
            self.parts.append(
                AutomatablePart(
                    ball.part,
                    "demo-ball",
                    display_location=Location(
                        (-self._config.size / 2 - self._config.size / 4, 0, 0)
                    ),
                    stl_folder=self._config.stl_folder,
                ),
            )

    print("Starting Partomatic configurator demo.")
    demo = DemoPart()
    demo._config.enable_step_exports = True
    demo.launch_configurator(
        host="0.0.0.0", port=8585, viewer_host="0.0.0.0", viewer_port=3939
    )
