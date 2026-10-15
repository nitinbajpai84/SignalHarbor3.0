import pytest

from m1_kit import World


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)
