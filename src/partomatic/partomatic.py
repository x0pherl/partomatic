__package__ = "partomatic"

"""Part extended for CI/CD automation"""

from dataclasses import field
from abc import ABC, abstractmethod
from pathlib import Path

from build123d import Location, export_stl

import ocp_vscode

import logging

from partomatic.partomatic_config import PartomaticConfig
from partomatic.automatable_part import AutomatablePart


class Partomatic(ABC):
    """
    Partomatic is an extension of the Compound class from build123d
    that allows for automation within a continuous integration
    environment. Descendant classes must implement:
    - compile: generating the geometry of components in the parts list
    """

    _config: PartomaticConfig
    parts: list[AutomatablePart] = field(default_factory=list)

    @abstractmethod
    def compile(self):
        """
        Builds the relevant parts for the partomatic part
        """

    def display(self):
        """
        Shows the relevant parts in OCP CAD Viewer
        """
        ocp_vscode.show(
            (
                [
                    part.part.move(Location(part.display_location))
                    for part in self.parts
                ]
            ),
            reset_camera=ocp_vscode.Camera.KEEP,
        )

    def complete_stl_file_path(self, part: AutomatablePart) -> str:
        return str(
            Path(
                Path(part.stl_folder)
                / f"{self._config.file_prefix}{part.file_name_base}{self._config.file_suffix}"
            ).with_suffix(".stl")
        )

    def export_stls(self):
        """
        Generates the relevant STLs in the configured
        folder
        """
        if self._config.stl_folder == "NONE":
            logging.getLogger("partomatic").warning(
                "stl_folder is set to NONE, skipping stl export"
            )
            return
        for part in self.parts:
            if not Path(self.complete_stl_file_path(part)).parent.exists():
                Path(self.complete_stl_file_path(part)).parent.mkdir(
                    parents=True,
                    exist_ok=self._config.create_folders_if_missing,
                )
            if (
                not Path(self.complete_stl_file_path(part)).parent.exists()
                or not Path(self.complete_stl_file_path(part)).parent.is_dir()
            ):
                error_str = f"Directory {Path(self.complete_stl_file_path(part)).parent} does not exist."
                logging.getLogger("partomatic").warning(error_str)
                raise FileNotFoundError(error_str)
            export_stl(part.part, self.complete_stl_file_path(part))

    def load_config(self, configuration: any, **kwargs):
        """
        loads a partomatic configuration from a file or valid yaml
        -------
        arguments:
            - configuration: the path to the configuration file
                OR
              a valid yaml configuration string
        """
        logging.getLogger("partomatic").debug(
            f"loading {configuration} with kwargs: {kwargs}"
        )
        self._config.load_config(configuration, **kwargs)

    def __init__(self, configuration: any = None, **kwargs):
        """
        loads a partomatic configuration from a file or valid yaml
        -------
        arguments:
            - configuration: the path to the configuration file
                OR
              a valid yaml configuration string
                OR
              None (default) for an empty object
            - **kwargs: specific fields to set in the configuration
        """
        self.parts = []
        # we have to call self.__class__.config so it can handle instanting
        # the descendant class of PartomaticConfig instead of using the generic
        # parent implementation
        self._config = self.__class__._config
        self.load_config(configuration, **kwargs)

    def partomate(self):
        """automates the part generation and exports stl and step models
         -------
        notes:
            - if you want to avoid exporting one of those file formats,
              you can override the export_stls or export_steps methods
              with a no-op method using the pass keyword
        """
        self.compile()
        self.export_stls()
