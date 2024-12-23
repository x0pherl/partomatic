"""Part extended for CI/CD automation"""

from dataclasses import dataclass, field, fields, is_dataclass, MISSING
from abc import ABC, abstractmethod
from pathlib import Path

from build123d import Part, Location, export_stl

import ocp_vscode

import yaml

from .partomatic_config import PartomaticConfig
from .automatable_part import AutomatablePart


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
                / f"{self._config.file_prefix}{part.file_name}{self._config.file_suffix}"
            ).with_suffix(".stl")
        )

    def export_stls(self):
        """
        Generates the relevant STLs in the configured
        folder
        """
        if self._config.stl_folder == "NONE":
            return
        for part in self.parts:
            Path(self.complete_stl_file_path(part)).parent.mkdir(
                parents=True, exist_ok=self._config.create_folders_if_missing
            )
            if (
                not Path(self.complete_stl_file_path(part)).parent.exists()
                or not Path(self.complete_stl_file_path(part)).parent.is_dir()
            ):
                raise FileNotFoundError(
                    f"Directory {Path(self.complete_stl_file_path(part)).parent} does not exist"
                )
            export_stl(part.part, self.complete_stl_file_path(part))

    def load_config(self, configuration: any, **kwargs):
        """
        loads a partomatic configuration from a file or valid yaml
        -------
        arguments:
            - configuration: the path to the configuration file
                OR
              a valid yaml configuration string
        -------
        notes:
            if yaml_tree is set in the PartomaticConfig descendent,
            PartomaticConfig will use that tree to find a node deep
            within the yaml tree, following the node names separated by slashes
            (example: "BigObject/Partomatic")
        """
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
        -------
        notes:
            you can assign yaml_tree as a kwarg here to load a
            configuration from a node node deep within the yaml tree,
            following the node names separated by slashes
            (example: "BigObject/Partomatic")
        """
        self.parts = []
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
