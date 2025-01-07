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
                step_folder=str(Path(self._config.stl_folder) / "steps"),
                create_folders=True,
            )
        )


class TestPartomatic:

    def test_partomatic_class(self, caplog):
        wc = WidgetConfig()
        assert wc.stl_folder == "C:\\Users\\xopher\\Downloads"
        foo = Widget(wc)
        assert foo._config.radius == 10
        assert foo._config.length == 17
        with (
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists"),
            patch("pathlib.Path.is_dir"),
            patch("ocp_vscode.show"),
            patch("build123d.export_stl"),
            patch("build123d.export_step"),
        ):
            foo.display()
            foo.partomate()
        foo._config.stl_folder = "NONE"
        foo.export_stls()
        assert len(caplog.records) > 0

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
