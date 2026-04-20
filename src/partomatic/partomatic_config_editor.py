"""Optional YAML/editor helpers for PartomaticConfig."""

from dataclasses import MISSING, fields, is_dataclass
from enum import Enum, Flag
from pathlib import Path
from threading import Thread
from typing import Any

import yaml


class PartomaticConfigEditorMixin:
    def _field_default(self, classfield):
        if classfield.default is not MISSING:
            return classfield.default
        if classfield.default_factory is not MISSING:
            return classfield.default_factory()
        return None

    def _to_primitive(self, value: Any):
        if isinstance(value, (Enum, Flag)):
            return value.name
        if is_dataclass(value):
            return {
                classfield.name: self._to_primitive(getattr(value, classfield.name))
                for classfield in fields(value.__class__)
            }
        if isinstance(value, list):
            return [self._to_primitive(item) for item in value]
        if isinstance(value, tuple):
            return [self._to_primitive(item) for item in value]
        if isinstance(value, dict):
            return {str(key): self._to_primitive(item) for key, item in value.items()}
        return value

    def as_dict(self) -> dict:
        """Serialize configuration fields to a plain dictionary."""
        return {
            classfield.name: self._to_primitive(getattr(self, classfield.name))
            for classfield in fields(self.__class__)
        }

    def _default_yaml_root(self) -> str:
        return self._clean_config_class_name.lower()

    def to_yaml(self, root_node: str = None) -> str:
        """Serialize configuration to Partomatic-compatible YAML."""
        node_name = root_node or self._default_yaml_root()
        return yaml.safe_dump({node_name: self.as_dict()}, sort_keys=False)

    def save_yaml(self, path: str, root_node: str = None):
        """Write configuration to a YAML file."""
        Path(path).write_text(self.to_yaml(root_node=root_node))

    def _constraint_map(self, classfield) -> dict:
        constraints = {}
        for key in (
            "ge",
            "gt",
            "le",
            "lt",
            "min_length",
            "max_length",
            "description",
            "step",
        ):
            if key in classfield.metadata:
                constraints[key] = classfield.metadata[key]
        return constraints

    def _editor_field_spec(self, field_type, value, classfield):
        if isinstance(field_type, type) and issubclass(field_type, (Enum, Flag)):
            return {
                "kind": "enum",
                "enum": [member.name for member in field_type],
                "value": self._to_primitive(value),
                "constraints": self._constraint_map(classfield),
            }
        if is_dataclass(field_type):
            nested_value = value if value is not None else field_type()
            return {
                "kind": "object",
                "fields": self._editor_spec_for_class(field_type, nested_value),
                "constraints": self._constraint_map(classfield),
            }
        type_name = "str"
        if field_type in (int, float, bool, str):
            type_name = field_type.__name__
        return {
            "kind": type_name,
            "value": self._to_primitive(value),
            "constraints": self._constraint_map(classfield),
        }

    def _editor_spec_for_class(self, cls, value_obj) -> dict:
        spec = {}
        for classfield in fields(cls):
            current_value = (
                getattr(value_obj, classfield.name)
                if value_obj is not None
                else self._field_default(classfield)
            )
            spec[classfield.name] = self._editor_field_spec(
                classfield.type,
                current_value,
                classfield,
            )
        return spec

    def _editor_spec(self) -> dict:
        return {
            "class_name": self.__class__.__name__,
            "root_node": self._default_yaml_root(),
            "fields": self._editor_spec_for_class(self.__class__, self),
        }

    def launch_editor(
        self,
        output_file: str = None,
        root_node: str = None,
        host: str = "localhost",
        port: int = 8501,
        background: bool = False,
    ):
        """Launch a web editor for this configuration.

        Requires optional dependencies:
            pip install partomatic[gui]

        Arguments:
            background: when True, run the UI server in a daemon thread and
                return the Thread object. Default False blocks the current
                process while serving the UI.
        """
        try:
            import nicegui  # noqa: F401
        except ModuleNotFoundError as ex:
            raise ModuleNotFoundError(
                "Missing optional GUI dependencies. Install with: pip install partomatic[gui]"
            ) from ex

        from .config_editor_app import run_editor

        spec = self._editor_spec()
        if root_node:
            spec["root_node"] = root_node

        if background:
            thread = Thread(
                target=run_editor,
                kwargs={
                    "spec": spec,
                    "output_file": output_file,
                    "host": host,
                    "port": port,
                },
                daemon=True,
                name="partomatic-config-editor",
            )
            thread.start()
            return thread

        return run_editor(
            spec=spec,
            output_file=output_file,
            host=host,
            port=port,
        )
