from dataclasses import dataclass, field
from enum import Enum, auto
from _pytest.logging import caplog
import pytest
from unittest.mock import patch
from pathlib import Path

from partomatic import AutomatablePart, PartomaticConfig, Partomatic
from build123d import BuildPart, Box, Part, Sphere, Align, Mode, Location

import logging
from sys import stdout


class FakeEnum(Enum):
    ONE = auto()
    TWO = auto()
    THREE = auto()


class SubConfig(PartomaticConfig):
    sub_field: str = "sub_default"
    sub_enum: FakeEnum = FakeEnum.ONE


class ContainerConfig(PartomaticConfig):
    container_field: str = "container_default"
    sub: SubConfig = field(default_factory=SubConfig)


class WidgetConfig(PartomaticConfig):
    stl_folder: str = field(default="C:\\Users\\xopher\\Downloads")
    radius: float = field(default=10)
    length: float = field(default=17)


class Widget(Partomatic):

    _config: WidgetConfig = WidgetConfig()

    def complete_wheel(self) -> Part:
        with BuildPart() as holebox:
            Box(
                self._config.length,
                self._config.length,
                self._config.length,
                align=(Align.CENTER, Align.CENTER, Align.CENTER),
            )
            Sphere(
                self._config.radius,
                align=(Align.CENTER, Align.CENTER, Align.CENTER),
                mode=Mode.SUBTRACT,
            )
        return holebox.part

    def compile(self):
        self.parts.clear()

        self.parts.append(
            AutomatablePart(
                self.complete_wheel(),
                "test",
                display_location=Location((9, 0, 9)),
                stl_folder=str(Path(self._config.stl_folder) / "stls"),
            )
        )


class TestPartomatic:

    def test_complete_file_path_helpers_and_wrap_compile_idempotent(self):
        foo = Widget()
        foo.compile()
        wrapped_compile = foo.compile

        stl_path = foo.complete_stl_file_path(foo.parts[0])
        step_path = foo.complete_step_file_path(foo.parts[0])

        assert stl_path.endswith(".stl")
        assert step_path.endswith(".step")

        foo._wrap_compile_method()
        assert foo.compile is wrapped_compile

    def test_dirty_state_tracks_config_against_last_compile(self):
        foo = Widget()

        assert foo.is_dirty is True

        foo.compile()
        assert foo.is_dirty is False

        foo._config.update_from_mapping({"radius": 12})
        assert foo.is_dirty is True

        foo._config.update_from_mapping({"radius": 10})
        assert foo.is_dirty is False

    def test_partomatic_class(self, caplog):
        wc = WidgetConfig()
        assert wc.stl_folder == "C:\\Users\\xopher\\Downloads"
        assert wc.enable_step_exports is False
        foo = Widget(wc)
        assert foo._config.radius == 10
        assert foo._config.length == 17
        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists"),
            patch("pathlib.Path.is_dir"),
            patch("ocp_vscode.show_clear"),
            patch("ocp_vscode.show"),
            patch("partomatic.partomatic.export_stl") as export_stl,
            patch("partomatic.partomatic.export_step") as export_step,
        ):
            foo.display()
            foo.partomate()
        export_stl.assert_called_once()
        export_step.assert_not_called()

        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists"),
            patch("pathlib.Path.is_dir"),
            patch("ocp_vscode.show_clear"),
            patch("partomatic.partomatic.export_stl") as export_stl,
            patch("partomatic.partomatic.export_step") as export_step,
        ):
            foo.partomate(export_steps=True)
        export_stl.assert_called_once()
        export_step.assert_called_once()
        foo._config.stl_folder = "NONE"
        foo.export_stls()
        foo.export_steps()
        assert len(caplog.records) > 0

    def test_export_to_directory_helpers_return_generated_paths(self):
        foo = Widget(stl_folder="relative-output")
        foo.compile()

        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.is_dir", return_value=True),
            patch("partomatic.partomatic.export_stl") as export_stl,
            patch("partomatic.partomatic.export_step") as export_step,
        ):
            stl_paths = foo.export_stls_to_directory("bundle")
            step_paths = foo.export_steps_to_directory("bundle")

        assert stl_paths[0].name.endswith(".stl")
        assert step_paths[0].name.endswith(".step")
        export_stl.assert_called_once()
        export_step.assert_called_once()

    def test_bad_stl_output_folder(self, caplog):
        logging.getLogger("partomatic").addHandler(logging.StreamHandler())
        foo = Widget(stl_folder="/bad/path")
        assert foo._config.stl_folder == "/bad/path"
        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.is_dir"),
            patch("ocp_vscode.show"),
            patch("build123d.export_stl"),
            patch("build123d.export_step"),
        ):
            foo.display()
            with pytest.raises(FileNotFoundError):
                foo.partomate()
        assert "does not exist" in caplog.records[-1].message
        assert "Directory" in caplog.records[-1].message

    def test_display_targets_configured_viewer_endpoint(self):
        foo = Widget()
        foo.compile()

        with patch("ocp_vscode.set_port") as set_port, patch(
            "ocp_vscode.show_clear"
        ), patch("ocp_vscode.show") as show:
            foo.display(viewer_host="127.0.0.1", viewer_port=4040)

        set_port.assert_called_once_with(4040, host="127.0.0.1")
        # show() is called without port parameter to use VS Code integration
        assert "port" not in show.call_args.kwargs

    def test_display_maintains_consistent_bounding_boxes(self):
        """Verify parts maintain consistent positions across multiple display calls."""
        from build123d import Location as BuildLocation

        foo = Widget()
        foo.compile()

        # Capture the bounding boxes from the first display
        with patch("ocp_vscode.show_clear"), patch("ocp_vscode.show") as show:
            foo.display()
            first_call_parts = show.call_args[0][0]
            first_bboxes = [part.bounding_box() for part in first_call_parts]

        # Call display again without changing config
        with patch("ocp_vscode.show_clear"), patch("ocp_vscode.show") as show:
            foo.display()
            second_call_parts = show.call_args[0][0]
            second_bboxes = [part.bounding_box() for part in second_call_parts]

        # Verify bounding boxes are identical across calls
        assert len(first_bboxes) == len(second_bboxes)
        for i, (first_bbox, second_bbox) in enumerate(zip(first_bboxes, second_bboxes)):
            # Check that min and max coordinates are the same
            first_min = first_bbox.min
            first_max = first_bbox.max
            second_min = second_bbox.min
            second_max = second_bbox.max

            assert (
                abs(first_min.X - second_min.X) < 1e-6
                and abs(first_min.Y - second_min.Y) < 1e-6
                and abs(first_min.Z - second_min.Z) < 1e-6
            ), f"Part {i} min coordinate changed: {first_min} -> {second_min}"

            assert (
                abs(first_max.X - second_max.X) < 1e-6
                and abs(first_max.Y - second_max.Y) < 1e-6
                and abs(first_max.Z - second_max.Z) < 1e-6
            ), f"Part {i} max coordinate changed: {first_max} -> {second_max}"

    def test_main_block(self):
        from unittest.mock import patch
        import runpy
        from pathlib import Path
        import os
        import sys

        script = str(Path(__file__).parents[1] / "src/partomatic/partomatic.py")
        src_root = str(Path(script).resolve().parents[1])
        script_dir = str(Path(script).resolve().parent)
        # Remove src_root so the insert branch fires; keep script_dir so the remove branch fires
        pruned_sys_path = [p for p in sys.path if os.path.abspath(p) != src_root] + [
            script_dir
        ]

        def fake_launch(self, **kwargs):
            self.compile()

        with patch(
            "partomatic.partomatic_preview.PartomaticPreviewMixin.launch_configurator",
            fake_launch,
        ), patch.object(sys, "path", pruned_sys_path):
            runpy.run_path(script, run_name="__main__")
            assert sys.path[0] == src_root
