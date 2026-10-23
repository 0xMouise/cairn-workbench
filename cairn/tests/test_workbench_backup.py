import importlib.util
import io
from pathlib import Path
import tarfile
import pytest
from cairn.workbench.store import Store


def load_script(name):
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_complete_backup_restore_and_traversal(tmp_path):
    script = load_script("backup_workbench")
    root = tmp_path / "original"
    store = Store(root)
    (root / "identity-key").write_bytes(b"test-key")
    (root / "projects").mkdir()
    (root / "projects/evidence.txt").write_text("evidence")
    archive = tmp_path / "backup.tar.gz"
    script.backup(root, archive)
    destination = tmp_path / "restored"
    script.restore(archive, destination)
    assert (destination / "projects/evidence.txt").read_text() == "evidence"
    assert (destination / "identity-key").read_bytes() == b"test-key"
    with pytest.raises(ValueError):
        script.restore(archive, destination)
    malicious = tmp_path / "malicious.tar.gz"
    with tarfile.open(malicious, "w:gz") as tar:
        member = tarfile.TarInfo("../escape")
        member.size = 4
        tar.addfile(member, io.BytesIO(b"evil"))
    with pytest.raises(ValueError):
        script.restore(malicious, tmp_path / "safe")
    assert not (tmp_path / "escape").exists()


def test_legacy_import_is_read_only_and_idempotent(tmp_path):
    import hashlib
    import sqlite3
    from cairn.server.db import SCHEMA

    script = load_script("migrate_legacy")
    source = tmp_path / "legacy.db"
    with sqlite3.connect(source) as c:
        c.executescript(SCHEMA)
        c.execute(
            "INSERT INTO projects(id,title,status,created_at) VALUES('project-1','legacy','completed','2026-10-23T00:00:00Z')"
        )
        c.execute("INSERT INTO facts VALUES('origin','project-1','original origin')")
        c.execute("INSERT INTO facts VALUES('goal','project-1','original goal')")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    assert script.migrate(source, tmp_path / "new") == 1
    assert script.migrate(source, tmp_path / "new") == 0
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    target = Store(tmp_path / "new")
    assert target.one("SELECT origin FROM wb_projects")["origin"] == "original origin"
