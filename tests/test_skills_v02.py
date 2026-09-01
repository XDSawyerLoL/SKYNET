from pathlib import Path

import pytest

from skynet.skills import SkillStore


def test_save_and_read_skill(tmp_path: Path) -> None:
    store = SkillStore(tmp_path / "skills")
    result = store.save_skill("prepare-stream", "# Prepare stream\n\n1. Open OBS.")
    assert "prepare-stream" in result
    assert store.read_skill("prepare-stream").startswith("# Prepare stream")
    assert store.list_skills() == ["prepare-stream"]


def test_reject_bad_skill_name(tmp_path: Path) -> None:
    store = SkillStore(tmp_path / "skills")
    with pytest.raises(ValueError):
        store.save_skill("../escape", "nope")
