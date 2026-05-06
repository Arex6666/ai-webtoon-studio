import pytest
from pathlib import Path
from unittest.mock import MagicMock

from app.services.agent.skills import lifecycle


def _mock_inst(install_id="i1", status="active", install_path=None, source_type="local"):
    m = MagicMock()
    m.id = install_id
    m.status = status
    m.install_path = install_path
    m.source_type = source_type
    return m


def test_disable_sets_status_and_unloads(monkeypatch):
    inst = _mock_inst(status="active")
    db = MagicMock()
    db.query.return_value.filter_by.return_value.one.return_value = inst
    called = []
    monkeypatch.setattr(lifecycle, "unload_skill", lambda i: called.append(i))
    out = lifecycle.disable(db, "i1")
    assert out.status == "disabled"
    assert called == ["i1"]


def test_disable_idempotent_when_already_disabled(monkeypatch):
    inst = _mock_inst(status="disabled")
    db = MagicMock()
    db.query.return_value.filter_by.return_value.one.return_value = inst
    called = []
    monkeypatch.setattr(lifecycle, "unload_skill", lambda i: called.append(i))
    out = lifecycle.disable(db, "i1")
    assert out.status == "disabled"
    assert called == []   # unload not called for idempotent path


def test_enable_validates_install_path():
    inst = _mock_inst(status="disabled", install_path=None)
    db = MagicMock()
    db.query.return_value.filter_by.return_value.one.return_value = inst
    with pytest.raises(ValueError, match="install_path"):
        lifecycle.enable(db, "i1")


def test_uninstall_marks_status_uninstalled(monkeypatch, tmp_path):
    p = tmp_path / "skill"
    p.mkdir()
    inst = _mock_inst(status="active", install_path=str(p), source_type="local")
    db = MagicMock()
    db.query.return_value.filter_by.return_value.one.return_value = inst
    monkeypatch.setattr(lifecycle, "unload_skill", lambda i: None)
    lifecycle.uninstall(db, "i1")
    assert inst.status == "uninstalled"
    assert not p.exists()


def test_uninstall_skips_filesystem_for_builtin(monkeypatch, tmp_path):
    p = tmp_path / "builtin_skill"
    p.mkdir()
    inst = _mock_inst(status="active", install_path=str(p), source_type="builtin")
    db = MagicMock()
    db.query.return_value.filter_by.return_value.one.return_value = inst
    monkeypatch.setattr(lifecycle, "unload_skill", lambda i: None)
    lifecycle.uninstall(db, "i1")
    assert inst.status == "uninstalled"
    assert p.exists()    # builtin path on disk preserved
