import pytest

from gate_kit import Kit


@pytest.fixture
def kit(tmp_path):
    return Kit(tmp_path)


@pytest.fixture
def world(kit):
    """Two industries, an unknown-industry company, an empty company and a solo company."""
    s = kit.store
    s.create_company("co-a", "Company A", "industry_a", package="build")      # m1-m5
    s.create_company("co-b", "Company B", "industry_b", package="discover")   # m1-m3
    s.create_company("co-n", "Company N", "none", modules=["m1_intent"])      # unknown industry
    s.create_company("co-empty", "Company Empty", "industry_a")               # nothing owned
    s.create_company("co-solo", "Solo Co", "industry_b", modules=["m2_baseline"])
    return kit
