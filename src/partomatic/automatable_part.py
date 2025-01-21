__package__ = "partomatic"
"""AutomatablePart is a dataclass that contains a Part object and additional inormation for saving and
displaying the part"""

from dataclasses import dataclass, field, fields, is_dataclass, MISSING
from pathlib import Path
from os import getcwd

from build123d import Part, Location


@dataclass
class AutomatablePart:
    """A dataclass that contains a Part object and additional information for
    saving and displaying the part
    ----------
    Arguments:
        - part: Part object to be saved and displayed
        - display_location: Location object to be used for displaying the part
        - stil_folder:
    """

    part: Part = field(default_factory=Part)
    display_location: Location = field(default_factory=Location)
    stl_folder: str = getcwd()
    _file_name_base: str = "partomatic"

    def __init__(self, part, file_name_base, **kwargs):
        """Initializes the AutomatablePart object
        ----------
        Arguments:
            - part: Part object to be saved and displayed
            - file_name_base: the base name of the part -- determines the name of an
            exported file when combined with the stl_folder and any suffixes and prefixes added
            - display_location (optional): Location object to be used for displaying the part
            - stil_folder (optional): the folder where the stl file will be saved. if not specified,
            the current working directory will be used
        """
        self.display_location = Location()
        self.file_name_base = file_name_base
        self.part = part
        if "display_location" in kwargs:
            display_location = kwargs["display_location"]
            if isinstance(display_location, Location):
                self.display_location = display_location
        if "stl_folder" in kwargs:
            self.stl_folder = kwargs["stl_folder"]

    @property
    def file_name_base(self) -> str:
        return self._file_name_base

    @file_name_base.setter
    def file_name_base(self, value: str):
        """
        Assigns the file name to the AutomatablePart, ensuring that no
        file extension is included.
        """
        self._file_name_base = Path(value).stem
