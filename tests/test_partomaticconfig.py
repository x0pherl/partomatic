from dataclasses import dataclass, field
from enum import Enum, auto
import pytest
from unittest.mock import patch
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

    def test_yaml_partomat(self):
        config = PartomaticConfig(self.config_yaml)
        assert config.stl_folder == "yaml_folder"

    def test_empty_partomat(self):
        config = PartomaticConfig()
        assert config.stl_folder == "NONE"

    def test_subconfig(self):
        config = SubConfig(self.blah_config_yaml, yaml_tree="Foo/Blah")
        assert config.stl_folder == "yaml_blah_folder"
        assert config.sub_field == "yaml_sub_field"
        assert config.sub_enum == FakeEnum.TWO

    def test_kwargs(self):
        config = SubConfig(yaml_tree="Part/Blah", sub_field="kwargsub")
        assert config.stl_folder == "NONE"
        assert config.sub_field == "kwargsub"

    def test_yaml_container_partomat(self):
        config = ContainerConfig(self.sub_config_yaml)
        assert config.container_field == "yaml_container_field"
        assert config.sub.sub_field == "yaml_sub_field"

    def test_invalid_config(self):
        with pytest.raises(ValueError):
            ContainerConfig("invalid_config")

    def test_yaml_container_with_dict_partomat(self):
        config = ContainerConfig(
            sub={
                "stl_folder": "yaml_blah_folder",
                "file_prefix": "yaml_blah_prefix",
                "file_suffix": "yaml_blah_suffix",
                "sub_field": "yaml_sub_field",
                "sub_enum": "TWO",
            }
        )
        assert config.sub.sub_field == "yaml_sub_field"

    def test_yaml_container_with_class_partomat(self):
        sub_config = SubConfig(self.blah_config_yaml, yaml_tree="Foo/Blah")

        config = ContainerConfig(sub=sub_config)
        assert config.sub.sub_field == "yaml_sub_field"

    def test_default_container_partomat(self):
        config = ContainerConfig()
        assert config.container_field == "container_default"
        assert config.sub.sub_field == "sub_default"

    def test_config_create(self):
        config = PartomaticConfig()
        config.stl_folder = "config_create_folder"
        config = PartomaticConfig(config)
        assert config.stl_folder == "config_create_folder"
