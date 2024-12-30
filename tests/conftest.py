import sys
import os
import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
)


@pytest.fixture
def wheel_config_yaml():
    return """
wheel:
    depth: 10
    radius: 30
    number: THREE
    bearing:
        radius: 4
        spindle_radius: 1.5
        number: TWO
        """
