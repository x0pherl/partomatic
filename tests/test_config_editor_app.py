import partomatic.config_editor_app as editor_app
from pathlib import Path


class _FakeElement:
    def __init__(self, value=None):
        self.value = value
        self.text = ""
        self._on_click = None
        self._on_value_change = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def classes(self, _value):
        return self

    def props(self, _value):
        return self

    def style(self, _value):
        return self

    def on_value_change(self, callback):
        self._on_value_change = callback
        return self

    def set_text(self, value):
        self.text = value


class _FakeUI:
    def __init__(self):
        self.buttons = []
        self.numbers = []
        self.last_notify = None
        self.last_run = None

    def column(self):
        return _FakeElement()

    def card(self):
        return _FakeElement()

    def row(self):
        return _FakeElement()

    def expansion(self, *_args, **_kwargs):
        return _FakeElement()

    def label(self, *_args, **_kwargs):
        return _FakeElement()

    def switch(self, _label, value=False):
        return _FakeElement(value=value)

    def number(self, _label, value=0, min=None, max=None, step=None):
        _ = min, max, step
        element = _FakeElement(value=value)
        self.numbers.append(element)
        return element

    def select(self, options, value=None, label=None):
        _ = label
        return _FakeElement(value=value if value is not None else options[0])

    def input(self, _label, value=""):
        return _FakeElement(value=value)

    def textarea(self, label=None):
        _ = label
        return _FakeElement(value="")

    def button(self, _label, on_click=None, **_kwargs):
        element = _FakeElement()
        element.text = _label
        element._on_click = on_click
        self.buttons.append(element)
        return element

    def notify(self, message, type=None):
        self.last_notify = (message, type)

    def run(self, **kwargs):
        self.last_run = kwargs
        kwargs["root"]()


def test_type_for_kind_all_variants():
    assert editor_app._type_for_kind("int") is int
    assert editor_app._type_for_kind("float") is float
    assert editor_app._type_for_kind("bool") is bool
    assert editor_app._type_for_kind("enum") is str
    assert editor_app._type_for_kind("anything") is str


def test_field_for_model_object_and_constraints():
    nested = editor_app._field_for_model(
        "child",
        {
            "kind": "object",
            "fields": {"x": {"kind": "int", "value": 3}},
        },
    )
    assert isinstance(nested, tuple)
    assert len(nested) == 2

    constrained = editor_app._field_for_model(
        "amount",
        {
            "kind": "float",
            "value": 1.2,
            "constraints": {"ge": 0.0, "le": 2.0, "step": 0.1, "junk": 5},
        },
    )
    assert constrained[0] is float

    enum_field = editor_app._field_for_model(
        "mode",
        {"kind": "enum", "enum": ["A", "B"], "value": "A"},
    )
    assert enum_field[0] is str


def test_render_collect_component_values(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(editor_app, "ui", fake_ui)

    fields = {
        "enabled": {"kind": "bool", "value": True},
        "count": {"kind": "int", "value": 2, "constraints": {"ge": 0, "le": 9}},
        "ratio": {
            "kind": "float",
            "value": 1.5,
            "constraints": {"ge": 0.0, "le": 5.0, "step": 0.5},
        },
        "mode": {"kind": "enum", "enum": ["A", "B"], "value": "B"},
        "name": {"kind": "str", "value": "abc"},
        "child": {
            "kind": "object",
            "fields": {
                "inner": {"kind": "str", "value": "z"},
            },
        },
    }

    state = {}
    tree = editor_app._collect_components(fields, state)
    values = editor_app._component_value(tree)
    assert values["enabled"] is True
    assert values["count"] == 2
    assert values["mode"] == "B"
    assert values["child"]["inner"] == "z"

    yaml_doc = editor_app._to_yaml_document("root", values)
    assert "root:" in yaml_doc
    assert "count: 2" in yaml_doc


def test_to_yaml_document_preserves_root_and_shape():
    yaml_doc = editor_app._to_yaml_document(
        "cfg",
        {
            "count": 5,
            "nested": {"enabled": True},
        },
    )

    assert "cfg:" in yaml_doc
    assert "count: 5" in yaml_doc
    assert "nested:" in yaml_doc
    assert "enabled: true" in yaml_doc


def test_run_editor_validation_then_save_path(monkeypatch):
    fake_ui = _FakeUI()
    monkeypatch.setattr(editor_app, "ui", fake_ui)

    writes = []
    monkeypatch.setattr(
        Path,
        "write_text",
        lambda self, text: writes.append((str(self), text)),
    )

    spec = {
        "class_name": "Cfg",
        "root_node": "cfg",
        "fields": {
            "count": {
                "kind": "int",
                "value": 5,
                "constraints": {"ge": 10},
            }
        },
    }

    editor_app.run_editor(spec, output_file="out.yaml", port=8604)

    count_component = fake_ui.numbers[0]
    count_component.value = 12
    count_component._on_value_change(None)

    save_button = next(
        button
        for button in fake_ui.buttons
        if button._on_click and "Save to out.yaml" in button.text
    )
    save_button._on_click()

    assert writes
    assert writes[-1][0].endswith("out.yaml")
    assert "cfg:" in writes[-1][1]
    assert "count: 12" in writes[-1][1]
    assert fake_ui.last_notify == ("Saved configuration to out.yaml", "positive")
