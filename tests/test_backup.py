import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("backup_project", Path(__file__).resolve().parents[1] / "scripts" / "backup_project.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_private_path_and_wikilinks_are_sanitized():
    source = "`" + "\\".join(["C:", "Users", "example-user", "notes"]) + "` [[laya-pokemon-experiment|研究]]"
    result = backup.sanitize(source)
    assert "example-user" not in result
    assert "[研究](preparation.md)" in result
    backup.validate_file("docs/test.md", result.encode())


@pytest.mark.parametrize("name,content", [
    ("roms/game.gb", b"rom"),
    (".env", b"private"),
    ("docs/key.md", ("ghp_" + "x" * 36).encode()),
    ("results/private.json", ("C:" + chr(92) + "Users" + chr(92) + "example-user").encode()),
])
def test_disallowed_artifacts_stop_backup(name, content):
    with pytest.raises(ValueError):
        backup.validate_file(name, content)


def test_json_escaped_private_path_is_also_rejected():
    import json
    path = "\\".join(["C:", "Users", "example-user", "private"])
    with pytest.raises(ValueError):
        backup.validate_file("results/example.json", json.dumps({"path": path}).encode())
