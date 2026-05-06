import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.services.agent.skills.installer import install_local, _find_skill_root
from app.services.agent.skills.manifest import ManifestError


def _make_skill(tmp_path):
    d = tmp_path / "test-skill"
    d.mkdir()
    (d / "skill.yaml").write_text("name: t\nversion: 1.0.0\ndescription: d\n", encoding="utf-8")
    return d


def test_find_skill_root_at_root(tmp_path):
    d = _make_skill(tmp_path)
    assert _find_skill_root(d) == d


def test_find_skill_root_one_level_deep(tmp_path):
    _make_skill(tmp_path)
    assert _find_skill_root(tmp_path).name == "test-skill"


def test_find_skill_root_raises_when_absent(tmp_path):
    with pytest.raises(ManifestError):
        _find_skill_root(tmp_path)


def test_install_local_rejects_non_directory(tmp_path):
    f = tmp_path / "not_a_dir.txt"
    f.write_text("x")
    db = MagicMock()
    with pytest.raises(ValueError, match="directory"):
        install_local(db, str(f))
