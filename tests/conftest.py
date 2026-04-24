import pytest
from tempfile import TemporaryDirectory


@pytest.fixture
def wheel_config_yaml():
    return f"""
wheel:
    stl_folder: {TemporaryDirectory().name}
    depth: 10
    radius: 30
    number: THREE
    bearing:
        radius: 4
        spindle_radius: 1.5
        number: TWO
        """
