"""NiceGUI configuration editor for PartomaticConfig objects."""

from pathlib import Path

from nicegui import ui
from pydantic import BaseModel, Field, ValidationError, create_model
import yaml


def _type_for_kind(kind: str):
    if kind == "int":
        return int
    if kind == "float":
        return float
    if kind == "bool":
        return bool
    if kind == "enum":
        return str
    return str


def _field_for_model(field_name: str, field_spec: dict):
    kind = field_spec.get("kind", "str")
    constraints = field_spec.get("constraints", {})
    if kind == "object":
        model_name = f"{field_name.title().replace('_', '')}Model"
        nested_model = _build_model(model_name, field_spec["fields"])
        return (nested_model, Field(default=None))

    default_value = field_spec.get("value")
    kwargs = {
        key: value
        for key, value in constraints.items()
        if key
        in (
            "ge",
            "gt",
            "le",
            "lt",
            "min_length",
            "max_length",
            "description",
        )
    }
    if kind == "enum":
        kwargs["description"] = kwargs.get(
            "description", "Select one allowed enum value"
        )
    return (_type_for_kind(kind), Field(default=default_value, **kwargs))


def _build_model(model_name: str, fields_spec: dict) -> type[BaseModel]:
    model_fields = {
        name: _field_for_model(name, field_spec)
        for name, field_spec in fields_spec.items()
    }
    return create_model(model_name, **model_fields)


def _render_field(path: str, name: str, field_spec: dict, form_state: dict):
    kind = field_spec.get("kind", "str")
    key = f"{path}.{name}"
    label = name.replace("_", " ").title()
    constraints = field_spec.get("constraints", {})

    if kind == "object":
        values = {}
        with ui.expansion(label, value=True).classes("w-full"):
            for nested_name, nested_spec in field_spec["fields"].items():
                values[nested_name] = _render_field(
                    f"{path}.{name}", nested_name, nested_spec, form_state
                )
        return values

    if kind == "bool":
        element = ui.switch(label, value=bool(field_spec.get("value", False)))
        form_state[key] = element
        return element

    if kind == "int":
        element = ui.number(
            label,
            value=int(field_spec.get("value", 0)),
            min=constraints.get("ge"),
            max=constraints.get("le"),
            step=1,
        )
        form_state[key] = element
        return element

    if kind == "float":
        element = ui.number(
            label,
            value=float(field_spec.get("value", 0.0)),
            min=constraints.get("ge"),
            max=constraints.get("le"),
            step=constraints.get("step", 0.1),
        )
        form_state[key] = element
        return element

    if kind == "enum":
        options = field_spec.get("enum", [])
        value = field_spec.get("value")
        element = ui.select(options=options, value=value or options[0], label=label)
        form_state[key] = element
        return element

    element = ui.input(label, value=str(field_spec.get("value", "")))
    form_state[key] = element
    return element


def _collect_components(fields_spec: dict, form_state: dict) -> dict:
    values = {}
    for name, field_spec in fields_spec.items():
        values[name] = _render_field("root", name, field_spec, form_state)
    return values


def _component_value(component_tree):
    if isinstance(component_tree, dict):
        return {
            key: _component_value(component)
            for key, component in component_tree.items()
        }
    return component_tree.value


def _to_yaml_document(root_node: str, data: dict) -> str:
    return yaml.safe_dump({root_node: data}, sort_keys=False)


def run_editor(
    spec: dict, output_file: str = None, host: str = "localhost", port: int = 8501
):
    class_name = spec.get("class_name", "PartomaticConfig")
    root_node = spec.get("root_node", "config")
    fields_spec = spec.get("fields", {})

    model = _build_model(f"{class_name}EditorModel", fields_spec)

    def build_ui():
        form_state = {}

        with ui.column().classes("w-full max-w-5xl mx-auto p-6 gap-4"):
            ui.label(f"{class_name} Editor").classes("text-3xl font-medium")
            ui.label("Nested configuration sections are collapsible.").classes(
                "text-sm text-slate-600"
            )

            with ui.card().classes("w-full"):
                ui.label("Configuration").classes("text-lg font-medium")
                component_tree = _collect_components(fields_spec, form_state)

            validation_label = ui.label().classes("text-red-700 whitespace-pre-wrap")
            yaml_preview = (
                ui.textarea(label="YAML Preview")
                .props("readonly")
                .classes("w-full h-96")
            )

            def refresh_preview():
                values = _component_value(component_tree)
                try:
                    validated = model.model_validate(values)
                    output_data = validated.model_dump(mode="python")
                    validation_label.set_text("")
                except ValidationError as ex:
                    output_data = values
                    validation_label.set_text(str(ex))
                yaml_preview.value = _to_yaml_document(root_node, output_data)

            def save_yaml():
                refresh_preview()
                if output_file:
                    Path(output_file).write_text(yaml_preview.value)
                    ui.notify(
                        f"Saved configuration to {output_file}",
                        type="positive",
                    )

            for component in form_state.values():
                component.on_value_change(lambda _event: refresh_preview())

            with ui.row().classes("gap-3"):
                ui.button("Refresh YAML", on_click=refresh_preview)
                if output_file:
                    ui.button(f"Save to {output_file}", on_click=save_yaml)
            refresh_preview()

    ui.run(host=host, port=port, reload=False, show=False, root=build_ui)
