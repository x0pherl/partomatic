__package__ = "partomatic"
"""AutomatablePart holds geometry and export/display metadata."""

from dataclasses import dataclass, field, fields, is_dataclass, MISSING
from pathlib import Path
from os import getcwd

from build123d import Part, Location


@dataclass
class AutomatablePart:
    """Contain a part and metadata used for display and export.

    Attributes:
        part: CAD part geometry.
        display_location: Placement used when rendering the part.
        stl_folder: Default export folder for generated files.
    """

    part: Part = field(default_factory=Part)
    display_location: Location = field(default_factory=Location)
    stl_folder: str = getcwd()
    _file_name_base: str = "partomatic"

    def __init__(
        self,
        part: Part,
        file_name_base: str,
        display_location: Location | None = None,
        stl_folder: str | None = None,
    ):
        """Initialize an automatable part wrapper.

        Args:
            part: CAD part to display/export.
            file_name_base: Base file name used during export (extension removed).
            display_location: Optional transform/location applied during display.
            stl_folder: Optional export folder. Defaults to current working directory.
        """
        self.display_location = Location()
        self.file_name_base = file_name_base
        self.part = part
        if display_location is not None and isinstance(display_location, Location):
            self.display_location = display_location
        if stl_folder is not None and isinstance(stl_folder, str):
            self.stl_folder = stl_folder

    @property
    def file_name_base(self) -> str:
        """Return the extension-free base file name for exports."""
        return self._file_name_base

    @file_name_base.setter
    def file_name_base(self, value: str):
        """Set the base file name, stripping any extension."""
        self._file_name_base = Path(value).stem
