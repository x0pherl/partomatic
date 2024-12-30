from dataclasses import dataclass, field
from enum import Enum, auto
import pytest
from unittest.mock import patch
from pathlib import Path

from partomatic import AutomatablePart
from build123d import BuildPart, Box, Sphere, Align, Mode, Location, Part


class TestAutomatablePart:
    def test_extension_removed(self):
        wheel_part = Part()
        wheel_automatable = AutomatablePart(wheel_part, "wheel.stl")
        assert wheel_automatable.file_name_base == "wheel"

    def test_kwargs(self):
        wheel_part = Part()
        wheel_automatable = AutomatablePart(
            wheel_part,
            "widget.stl",
            display_location=Location((100, 100, 100)),
            stl_folder="/tmp/test/folder",
        )
        assert wheel_automatable.display_location.position.X == 100
        assert wheel_automatable.stl_folder == "/tmp/test/folder"
