from dataclasses import dataclass, field, fields as dataclass_fields
from enum import Enum, auto
import pytest
from unittest.mock import patch
from pathlib import Path
from types import ModuleType
import sys
from partomatic import PartomaticConfig
import yaml


class FakeEnum(Enum):
    ONE = auto()
    TWO = auto()
    THREE = auto()


class SubConfig(PartomaticConfig):
    sub_field: str = "sub_default"
    sub_enum: FakeEnum = FakeEnum.ONE


class ContainerConfig(PartomaticConfig):
    container_field: str = "container_default"
    sub: SubConfig = field(default_factory=SubConfig)


class BearingConfig(PartomaticConfig):
    radius: float = 10
    spindle_radius: float = 2
    number: FakeEnum = FakeEnum.ONE


class WheelConfig(PartomaticConfig):
    depth: float = 2
    radius: float = 50
    number: FakeEnum = FakeEnum.ONE
    bearing: BearingConfig = field(default_factory=BearingConfig)


class TestPartomaticConfig:

    def test_load_yaml_wheel(self, wheel_config_yaml):
        config = WheelConfig(wheel_config_yaml)
        assert config.depth == 10
        assert config.radius == 30
        assert config.bearing.__class__ == BearingConfig
        assert config.bearing.radius == 4
        assert config.bearing.spindle_radius == 1.5
        assert config.bearing.number == FakeEnum.TWO

    def test_load_yaml_wheel_from_file(self, wheel_config_yaml):
        mock_file_path = "mock_wheel_config.yaml"
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "is_file", return_value=True):
                with patch.object(Path, "read_text", return_value=wheel_config_yaml):
                    config = WheelConfig(mock_file_path)
                    assert config.depth == 10
                    assert config.radius == 30
                    assert config.bearing.__class__ == BearingConfig
                    assert config.bearing.radius == 4
                    assert config.bearing.spindle_radius == 1.5

    def test_post_init_called(self):
        class ChildConfig(PartomaticConfig):
            component_value: float = 5
            derived_value: float = 0

        class ParentConfig(PartomaticConfig):
            parent_value: float = 20
            child: ChildConfig = field(default_factory=ChildConfig)

            def __post_init__(self):
                self.child.derived_value = (
                    self.parent_value / self.child.component_value
                )

        parent = ParentConfig()
        assert parent.child.derived_value == 4.0

    def test_instantiating_with_object(self, wheel_config_yaml):
        base_wheel = WheelConfig(wheel_config_yaml)
        config = WheelConfig(base_wheel)
        assert config.depth == 10
        assert config.radius == 30
        assert config.bearing.__class__ == BearingConfig
        assert config.bearing.radius == 4
        assert config.bearing.spindle_radius == 1.5

    def test_no_default_descendant(self):
        class BadConfig(PartomaticConfig):
            no_default: float

        with pytest.raises(ValueError):
            x = BadConfig()

    def test_bad_yaml_config(self):
        yaml = """
test:
    field: 2
    sub_test:
        sub_field: 3
"""
        with pytest.raises(ValueError):
            config = WheelConfig(yaml)

    def test_nested_load(self):
        car_yaml = """
car:
    car_param_1: 1
    drivetrain:
        drive_train_param_1: 2
        wheel:
            depth: 10
            radius: 30
            bearing:
                radius: 4.7
                spindle_radius: 1.5
"""
        wheel_config = WheelConfig(
            {"wheel": yaml.safe_load(car_yaml)["car"]["drivetrain"]["wheel"]}
        )
        assert wheel_config.bearing.radius == 4.7

    def test_passed_params(self):
        bearing_config = BearingConfig(radius=20.6, spindle_radius=10)
        wheel_config = WheelConfig(depth=5, radius=50.2, bearing=bearing_config)
        assert wheel_config.bearing.radius == 20.6
        assert wheel_config.radius == 50.2

    def test_sub_dict(self):
        config = WheelConfig(
            bearing={
                "file_prefix": "yaml_blah_prefix",
                "file_suffix": "yaml_blah_suffix",
                "radius": 88.2,
                "spindle_radius": 44.1,
                "number": "TWO",
            }
        )
        assert config.bearing.radius == 88.2
        assert config.bearing.number == FakeEnum.TWO

    def test_default_wheel(self):
        config = WheelConfig()
        assert config.depth == 2
        assert config.radius == 50
        assert config.bearing.radius == 10
        assert config.bearing.spindle_radius == 2

    def test_config_node(self):
        yaml = """
WheelConfig:
    depth: 10
    radius: 30
    number: THREE
    bearing:
        radius: 4
        spindle_radius: 7.3
        number: TWO
        """
        config = WheelConfig(yaml)
        assert config.bearing.spindle_radius == 7.3

    def test_lower_config_node(self):
        yaml = """
wheelconfig:
    depth: 10
    radius: 30
    number: THREE
    bearing:
        radius: 4
        spindle_radius: 7.3
        number: TWO
        """
        config = WheelConfig(yaml)
        assert config.bearing.spindle_radius == 7.3

    def test_lower_configless_node(self):
        yaml = """
Wheel:
    depth: 10
    radius: 30
    number: THREE
    bearing:
        radius: 4
        spindle_radius: 7.3
        number: TWO
        """
        config = WheelConfig(yaml)
        assert config.bearing.spindle_radius == 7.3

    def test_enum_kwarg(self):
        config = WheelConfig(number=FakeEnum.THREE)
        assert config.number == FakeEnum.THREE

    def test_yaml_round_trip(self, wheel_config_yaml):
        original = WheelConfig(wheel_config_yaml)
        reloaded = WheelConfig(original.to_yaml())
        assert reloaded.depth == original.depth
        assert reloaded.radius == original.radius
        assert reloaded.number == original.number
        assert reloaded.bearing.radius == original.bearing.radius

    def test_configuration_and_kwargs_combined(self, wheel_config_yaml):
        config = WheelConfig(wheel_config_yaml, radius=99.9)
        assert config.radius == 99.9
        assert config.depth == 10

    def test_enum_string_kwarg(self):
        config = WheelConfig(number="THREE")
        assert config.number == FakeEnum.THREE

    def test_editor_field_default_helper(self):
        @dataclass
        class RawDefaults:
            required: int
            with_default: int = 5
            with_factory: list = field(default_factory=list)

        config = WheelConfig()
        raw_fields = {f.name: f for f in dataclass_fields(RawDefaults)}

        assert config._field_default(raw_fields["with_default"]) == 5
        assert config._field_default(raw_fields["with_factory"]) == []
        assert config._field_default(raw_fields["required"]) is None

    def test_editor_to_primitive_for_collections(self):
        class CollectionConfig(PartomaticConfig):
            items: list = field(default_factory=lambda: [FakeEnum.ONE, FakeEnum.TWO])
            pair: tuple = (FakeEnum.ONE, 7)
            mapping: dict = field(default_factory=lambda: {"k": FakeEnum.THREE})

        config = CollectionConfig()
        result = config.as_dict()

        assert result["items"] == ["ONE", "TWO"]
        assert result["pair"] == ["ONE", 7]
        assert result["mapping"] == {"k": "THREE"}

    def test_editor_spec_includes_constraints(self):
        class SpecConfig(PartomaticConfig):
            amount: float = field(
                default=1.5,
                metadata={
                    "ge": 0.0,
                    "le": 2.0,
                    "description": "Amount",
                    "step": 0.01,
                },
            )
            label: str = field(
                default="abc", metadata={"min_length": 1, "max_length": 5}
            )
            mode: FakeEnum = FakeEnum.ONE
            sub: SubConfig = field(default_factory=SubConfig)

        spec = SpecConfig()._editor_spec()

        assert spec["class_name"] == "SpecConfig"
        assert spec["root_node"] == "spec"
        assert spec["fields"]["amount"]["kind"] == "float"
        assert spec["fields"]["amount"]["constraints"]["step"] == 0.01
        assert spec["fields"]["label"]["constraints"]["min_length"] == 1
        assert spec["fields"]["mode"]["kind"] == "enum"
        assert spec["fields"]["sub"]["kind"] == "object"

    def test_save_yaml_writes_expected_text(self):
        config = WheelConfig()

        with patch.object(Path, "write_text") as write_text:
            config.save_yaml("wheel.yaml", root_node="wheel")

        write_text.assert_called_once()
        yaml_text = write_text.call_args[0][0]
        assert "wheel:" in yaml_text
        assert "radius: 50" in yaml_text

    def test_launch_editor_missing_gui_dependency(self, monkeypatch):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "nicegui":
                raise ModuleNotFoundError("No module named 'nicegui'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", fake_import)

        with pytest.raises(ModuleNotFoundError, match="partomatic\\[gui\\]"):
            WheelConfig().launch_editor()

    def test_launch_editor_foreground_and_background(self):
        calls = []

        def fake_run_editor(**kwargs):
            calls.append(kwargs)
            return "ok"

        fake_app_module = ModuleType("partomatic.config_editor_app")
        fake_app_module.run_editor = fake_run_editor
        fake_nicegui_module = ModuleType("nicegui")

        config = WheelConfig()
        with patch.dict(
            sys.modules,
            {
                "partomatic.config_editor_app": fake_app_module,
                "nicegui": fake_nicegui_module,
            },
        ):
            result = config.launch_editor(
                output_file="wheel.yaml",
                root_node="wheel_override",
                host="127.0.0.1",
                port=9001,
            )
            assert result == "ok"
            assert calls[-1]["spec"]["root_node"] == "wheel_override"

            thread = config.launch_editor(background=True)
            thread.join(timeout=1)
            assert thread.name == "partomatic-config-editor"
            assert calls[-1]["port"] == 8501
