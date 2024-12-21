from dataclasses import dataclass, field
from enum import Enum, auto
import pytest
from unittest.mock import patch
from pathlib import Path

from partomatic import BuildablePart
from build123d import BuildPart, Box, Sphere, Align, Mode, Location, Part


class TestBuildablePart:
    def test_extension_removed(self):
        widget_part = Part()
        widget = BuildablePart(widget_part, "widget.stl")
        assert widget.file_name == "widget"
