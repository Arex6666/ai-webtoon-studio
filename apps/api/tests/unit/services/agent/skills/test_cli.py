import pytest
from app.services.agent.skills import cli


def test_validate_cmd_runs_on_valid_skill(tmp_path, capsys):
    d = tmp_path / "skill"
    d.mkdir()
    (d / "skill.yaml").write_text("name: ok\nversion: 1.0.0\ndescription: d\n")
    cli.main(["validate", str(d)])
    out = capsys.readouterr().out
    assert "OK: ok@1.0.0" in out


def test_validate_cmd_fails_on_invalid_manifest(tmp_path):
    d = tmp_path / "skill"
    d.mkdir()
    (d / "skill.yaml").write_text("name: ok\n")  # missing version, description
    with pytest.raises(Exception):
        cli.main(["validate", str(d)])
