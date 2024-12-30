from dataclasses import dataclass, field
from enum import Enum, auto
import pytest
from unittest.mock import mock_open, patch
from pathlib import Path
from partomatic import PartomaticConfig


from build123d import BuildPart, Box, Sphere, Align, Mode, Location, Part


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
    yaml_tree: str = "wheel/bearing"
    radius: float = 10
    spindle_radius: float = 2
    number: FakeEnum = FakeEnum.ONE


class WheelConfig(PartomaticConfig):
    yaml_tree = "wheel"
    depth: float = 2
    radius: float = 50
    number: FakeEnum = FakeEnum.ONE
    bearing: BearingConfig = field(default_factory=BearingConfig)


class TestPartomaticConfig:
    config_yaml = """
Part:
    stl_folder: "yaml_folder"
    file_prefix: "yaml_prefix"
    file_suffix: "yaml_suffix"
"""
    blah_config_yaml = """
Foo:
    container_field: "yaml_container_field"
    Blah:
        stl_folder: "yaml_blah_folder"
        file_prefix: "yaml_blah_prefix"
        file_suffix: "yaml_blah_suffix"
        sub_field: "yaml_sub_field"
        sub_enum: "TWO"
"""

    sub_config_yaml = """
Part:
    container_field: "yaml_container_field"
    sub:
        stl_folder: "yaml_blah_folder"
        file_prefix: "yaml_blah_prefix"
        file_suffix: "yaml_blah_suffix"
        sub_field: "yaml_sub_field"
        sub_enum: "TWO"
"""

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
                with patch.object(
                    Path, "read_text", return_value=wheel_config_yaml
                ):
                    config = WheelConfig(mock_file_path)
                    assert config.depth == 10
                    assert config.radius == 30
                    assert config.bearing.__class__ == BearingConfig
                    assert config.bearing.radius == 4
                    assert config.bearing.spindle_radius == 1.5

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
            yaml_tree = "wheel"
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
        wheel_config = WheelConfig(car_yaml, yaml_tree="car/drivetrain/wheel")
        assert wheel_config.bearing.radius == 4.7

    def test_passed_params(self):
        bearing_config = BearingConfig(radius=20.6, spindle_radius=10)
        wheel_config = WheelConfig(
            depth=5, radius=50.2, bearing=bearing_config
        )
        assert wheel_config.bearing.radius == 20.6
        assert wheel_config.radius == 50.2

    def test_sub_dict(self):
        config = WheelConfig(
            bearing={
                "yaml_tree": "wheel/bearing",
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
