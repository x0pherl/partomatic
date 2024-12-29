from dataclasses import dataclass, field
from enum import Enum, auto
import pytest
from unittest.mock import patch
from pathlib import Path

from partomatic import AutomatablePart
from build123d import BuildPart, Box, Sphere, Align, Mode, Location, Part


class TestAutomatablePart:
    def test_extension_removed(self):
        widget_part = Part()
        widget = AutomatablePart(widget_part, "widget.stl")
        assert widget.file_name == "widget"

    def test_extension_removed(self):
        widget_part = Part()
        widget = AutomatablePart(widget_part, "widget.stl")
        assert widget.file_name == "widget"
