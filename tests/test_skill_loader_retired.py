from sh_platform.plane import PlaneStore
from sh_platform.v1 import skill_loader


def test_override_saved_under_retired_name_still_applies(tmp_path):
    plane = PlaneStore(tmp_path).create("acme")
    old = plane.path("skills", "flow")
    old.mkdir(parents=True)
    (old / "playbook.md").write_text("OLD OVERRIDE", encoding="utf-8")
    assert "OLD OVERRIDE" in skill_loader.load_skill("span", plane)
    new = plane.path("skills", "span")
    new.mkdir(parents=True)
    (new / "playbook.md").write_text("NEW OVERRIDE", encoding="utf-8")
    text = skill_loader.load_skill("flow", plane)
    assert "NEW OVERRIDE" in text and "OLD OVERRIDE" not in text
