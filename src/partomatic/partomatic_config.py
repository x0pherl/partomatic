__package__ = "partomatic"
"""Configuration model and loaders for Partomatic objects."""

from dataclasses import field, fields, is_dataclass, MISSING
from enum import Enum, Flag
from pathlib import Path
from typing import ClassVar, get_origin

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
        new_cls = pydantic_dataclass(kw_only=True, repr=False)(new_cls)

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
    """Base configuration model for Partomatic workflows.

    This class provides an automatic introspection-based ``__repr__`` that
    prints annotated fields and public properties in separate sections.
    Subclasses can tune output behavior with class variables:

    - ``_verbose_repr``: enable/disable sectioned verbose output.
    - ``_repr_float_precision``: significant digits used for float formatting.
    - ``_repr_max_value_length``: max rendered value length before truncation.
    """

    _repr_float_precision: ClassVar[int] = 4
    _repr_max_value_length: ClassVar[int] = 120

    stl_folder: str = "NONE"
    enable_step_exports: bool = False
    file_prefix: str = ""
    file_suffix: str = ""
    create_folders_if_missing: bool = True

    def _iter_annotated_field_names(self) -> list[str]:
        """Return unique public annotated field names from the class hierarchy."""
        names: list[str] = []
        for klass in reversed(self.__class__.__mro__):
            annotations = getattr(klass, "__annotations__", {}) or {}
            for name, annotated_type in annotations.items():
                if name.startswith("_"):
                    continue
                if get_origin(annotated_type) is ClassVar:
                    continue
                if name not in names:
                    names.append(name)
        return names

    def _iter_property_names(self) -> list[str]:
        """Return unique public property names from the class hierarchy."""
        names: list[str] = []
        for klass in reversed(self.__class__.__mro__):
            for name, member in klass.__dict__.items():
                if name.startswith("_"):
                    continue
                if isinstance(member, property) and name not in names:
                    names.append(name)
        return names

    def _safe_getattr(self, name: str):
        """Fetch an attribute and convert failures into a readable marker."""
        try:
            return getattr(self, name)
        except Exception as error:  # pragma: no cover - exercised via repr tests
            return f"<error: {error.__class__.__name__}: {error}>"

    def _repr_value(self, value, seen: set[int] | None = None, depth: int = 2) -> str:
        """Render values safely for ``__repr__`` output."""
        if seen is None:
            seen = set()

        if isinstance(value, float):
            precision = max(1, int(getattr(self, "_repr_float_precision", 4)))
            rendered = format(value, f".{precision}g")
        elif isinstance(value, dict):
            if depth <= 0:
                rendered = "{...}"
            else:
                obj_id = id(value)
                if obj_id in seen:
                    rendered = "{<circular-ref>}"
                else:
                    seen.add(obj_id)
                    rendered = (
                        "{"
                        + ", ".join(
                            f"{self._repr_value(key, seen, depth - 1)}: {self._repr_value(val, seen, depth - 1)}"
                            for key, val in value.items()
                        )
                        + "}"
                    )
                    seen.remove(obj_id)
        elif isinstance(value, (list, tuple, set)):
            if depth <= 0:
                if isinstance(value, list):
                    rendered = "[...]"
                elif isinstance(value, tuple):
                    rendered = "(...)"
                else:
                    rendered = "{...}"
            else:
                obj_id = id(value)
                if obj_id in seen:
                    rendered = "<circular-ref>"
                else:
                    seen.add(obj_id)
                    inner = ", ".join(
                        self._repr_value(item, seen, depth - 1) for item in value
                    )
                    if isinstance(value, list):
                        rendered = f"[{inner}]"
                    elif isinstance(value, tuple):
                        if len(value) == 1:
                            rendered = f"({inner},)"
                        else:
                            rendered = f"({inner})"
                    else:
                        rendered = f"{{{inner}}}"
                    seen.remove(obj_id)
        else:
            rendered = repr(value)

        max_len = max(16, int(getattr(self, "_repr_max_value_length", 120)))
        if len(rendered) > max_len:
            rendered = f"{rendered[: max_len - 3]}..."
        return rendered

    def _default_repr(self) -> str:
        """Return a compact dataclass-field-only representation."""
        bits = [
            f"{field_info.name}={self._repr_value(getattr(self, field_info.name))}"
            for field_info in fields(self)
            if not field_info.name.startswith("_")
        ]
        return f"{self.__class__.__name__}({', '.join(bits)})"

    def __repr__(self) -> str:
        """Return a robust, sectioned representation of config state."""

        field_lines = []
        for name in self._iter_annotated_field_names():
            value = self._safe_getattr(name)
            field_lines.append(f"    {name}={self._repr_value(value)}")

        property_lines = []
        field_names = set(self._iter_annotated_field_names())
        for name in self._iter_property_names():
            if name in field_names:
                continue
            value = self._safe_getattr(name)
            property_lines.append(f"    {name}={self._repr_value(value)}")

        sections = []
        if field_lines:
            sections.append("  Fields:\n" + "\n".join(field_lines))
        if property_lines:
            sections.append("  Properties:\n" + "\n".join(property_lines))

        if not sections:
            return f"{self.__class__.__name__}()"

        return f"{self.__class__.__name__}(\n" + "\n".join(sections) + "\n)"

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
