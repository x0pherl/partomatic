__package__ = "partomatic"
"""Configuration model and loaders for Partomatic objects."""

from dataclasses import field, fields, is_dataclass, MISSING
from enum import Enum, Flag
from pathlib import Path

from pydantic.dataclasses import dataclass as pydantic_dataclass
import yaml

if __name__ == "__main__":
    import os, sys

    script_dir = os.path.dirname(os.path.abspath(__file__))
    src_root = os.path.dirname(script_dir)
    # Remove the script directory so 'partomatic' resolves to the package, not this file
    if script_dir in sys.path:
        sys.path.remove(script_dir)
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

from partomatic.partomatic_config_editor import PartomaticConfigEditorMixin


class AutoDataclassMeta(type):
    """Metaclass that applies pydantic dataclass behavior to subclasses."""

    def __new__(cls, name, bases, dct):
        """Create a class wrapped as a keyword-only pydantic dataclass.

        Args:
            cls: Metaclass type.
            name: Class name being created.
            bases: Base classes for the new class.
            dct: Class namespace dictionary.

        Returns:
            Newly created class with dataclass conversion applied.
        """
        original_init = dct.get("__init__")
        new_cls = super().__new__(cls, name, bases, dct)
        new_cls = pydantic_dataclass(kw_only=True)(new_cls)

        if original_init is not None:
            new_cls.__init__ = original_init
        else:
            for base in bases:
                inherited_init = getattr(base, "__init__", None)
                if inherited_init and inherited_init is not object.__init__:
                    new_cls.__init__ = inherited_init
                    break

        return new_cls


class PartomaticConfig(PartomaticConfigEditorMixin, metaclass=AutoDataclassMeta):
    """Base configuration model for Partomatic workflows."""

    stl_folder: str = "NONE"
    enable_step_exports: bool = False
    file_prefix: str = ""
    file_suffix: str = ""
    create_folders_if_missing: bool = True

    @property
    def _clean_config_class_name(self) -> str:
        """Return class name without a trailing "Config" suffix."""
        name = self.__class__.__name__
        if name.lower().endswith("config"):
            name = name[:-6]
        return name

    def _default_config(self):
        """Reset all fields to declared defaults."""
        for field in fields(self):
            if field.default is not MISSING:
                setattr(self, field.name, field.default)
            elif field.default_factory is not MISSING:
                setattr(self, field.name, field.default_factory())
            else:
                raise ValueError(f"Field {field.name} has no default value")

    def load_config(self, configuration: any, **kwargs):
        """Load configuration values from object, YAML text, or YAML file.

        Args:
            configuration: Another instance of this config class, a YAML string,
                a path to a YAML file, or `None`.
            **kwargs: Field overrides applied after loading `configuration`.
        """
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
            if self.__class__.__name__ in bracket_dict:
                bracket_dict = bracket_dict[self.__class__.__name__]
            elif self.__class__.__name__.lower() in bracket_dict:
                bracket_dict = bracket_dict[self.__class__.__name__.lower()]
            elif self._clean_config_class_name in bracket_dict:
                bracket_dict = bracket_dict[self._clean_config_class_name]
            elif self._clean_config_class_name.lower() in bracket_dict:
                bracket_dict = bracket_dict[self._clean_config_class_name.lower()]
            else:
                raise ValueError(
                    f"Configuration file does not contain a node for {self.__class__.__name__}"
                )

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
                    elif is_dataclass(classfield.type) and isinstance(value, dict):
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
                    elif (
                        (not isinstance(value, classfield.type))
                        and isinstance(classfield.type, type)
                        and issubclass(classfield.type, (Enum, Flag))
                    ):
                        setattr(
                            self,
                            classfield.name,
                            classfield.type[value.upper()],
                        )
                    else:
                        setattr(self, key, value)

    def __init__(self, configuration: any = None, **kwargs):
        """Initialize configuration with defaults, source data, and overrides.

        Args:
            configuration: Optional source passed to `load_config`.
            **kwargs: Optional field overrides passed to `load_config`.
        """
        if configuration is not None or kwargs:
            self.load_config(configuration=configuration, **kwargs)
        else:
            self._default_config()
        self.__post_init__()

    def __post_init__(self):
        """Hook for subclasses to recompute derived values after load/update."""
        pass


if __name__ == "__main__":

    class DemoConfig(PartomaticConfig):
        stl_folder: str = "NONE"
        size: float = 20.0
        sphere_ratio: float = field(
            default=0.6,
            metadata={
                "kind": "float",
                "constraints": {"ge": 0.1, "le": 1.0},
                "step": 0.01,
            },
        )

    config = DemoConfig()
    config.launch_editor()
