"""Part extended for CI/CD automation"""

from dataclasses import dataclass, field, fields, is_dataclass, MISSING
from enum import Enum, Flag
from pathlib import Path

import yaml


class AutoDataclassMeta(type):
    def __new__(cls, name, bases, dct):
        new_cls = super().__new__(cls, name, bases, dct)
        return dataclass(init=False)(new_cls)


@dataclass
class PartomaticConfig(metaclass=AutoDataclassMeta):
    yaml_tree: str = "Part"
    stl_folder: str = "NONE"
    file_prefix: str = ""
    file_suffix: str = ""
    create_folders_if_missing: bool = True

    def _default_config(self):
        """
        Resets all values to their default values.
        """
        for field in fields(self):
            if field.default is not MISSING:
                setattr(self, field.name, field.default)
            elif field.default_factory is not MISSING:
                setattr(self, field.name, field.default_factory())
            else:
                raise ValueError(f"Field {field.name} has no default value")

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
        if "yaml_tree" in kwargs:
            self.yaml_tree = kwargs["yaml_tree"]
        if isinstance(configuration, self.__class__):
            for field in fields(self):
                setattr(self, field.name, getattr(configuration, field.name))
            return
        if configuration is not None:
            configuration = str(configuration)
            if "\n" not in configuration:
                path = Path(configuration)
                if path.exists() and path.is_file():
                    configuration = path.read_text()
            bracket_dict = yaml.safe_load(configuration)
            for node in self.yaml_tree.split("/"):
                if node not in bracket_dict:
                    raise ValueError(
                        f"Node {node} not found in configuration file"
                    )
                bracket_dict = bracket_dict[node]

            for classfield in fields(self.__class__):
                if classfield.name in bracket_dict:
                    value = bracket_dict[classfield.name]
                    if isinstance(classfield.type, type) and issubclass(
                        classfield.type, (Enum, Flag)
                    ):
                        setattr(
                            self,
                            classfield.name,
                            classfield.type[value.upper()],
                        )
                    elif is_dataclass(classfield.type) and isinstance(
                        value, dict
                    ):
                        setattr(
                            self,
                            classfield.name,
                            classfield.type(**value),
                        )
                    else:
                        setattr(self, classfield.name, value)
        if kwargs:
            for key, value in kwargs.items():
                classfield = next(
                    (f for f in fields(self.__class__) if f.name == key),
                    None,
                )
                if classfield:
                    if is_dataclass(classfield.type):
                        if isinstance(value, dict):
                            setattr(self, key, classfield.type(**value))
                        else:
                            setattr(self, key, value)
                    elif isinstance(classfield.type, type) and issubclass(
                        classfield.type, (Enum, Flag)
                    ):
                        setattr(
                            self,
                            classfield.name,
                            classfield.type[value.upper()],
                        )
                    else:
                        setattr(self, key, value)

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
        if "yaml_tree" in kwargs:
            self.yaml_tree = kwargs["yaml_tree"]
        if configuration is not None:
            self.load_config(configuration, yaml_tree=self.yaml_tree)
        elif kwargs:
            self.load_config(configuration=configuration, **kwargs)
        else:
            self._default_config()
