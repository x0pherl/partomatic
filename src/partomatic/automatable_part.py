"""AutomatablePart is a dataclass that contains a Part object and additional inormation for saving and
displaying the part"""

from dataclasses import dataclass, field, fields, is_dataclass, MISSING
from pathlib import Path
from os import getcwd

from build123d import Part, Location


@dataclass
class AutomatablePart():
    part: Part = field(default_factory=Part)
    display_location: Location = field(default_factory=Location)
    stl_folder: str = getcwd()
    #todo this should not be file_name, maybe _file_name_base
    _file_name: str = "partomatic"

    def __init__(self, part, file_name, **kwargs):
        self.display_location = Location()
        self.file_name = file_name
        self.part = part
        if "display_location" in kwargs:
            display_location = kwargs["display_location"]
            if isinstance(display_location, Location):
                self.display_location = display_location
        if "stl_folder" in kwargs:
            self.stl_folder = kwargs["stl_folder"]

    @property
    def file_name(self) -> str:
        return self._file_name

    @file_name.setter
    def file_name(self, value: str):
        """
        Assigns the file name to the AutomatablePart, ensuring that no
        file extension is included.
        """
        self._file_name = Path(value).stem
