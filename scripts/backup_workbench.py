"""Offline complete backup / restore. Stop the Workbench service before restoring."""

import argparse
from pathlib import Path
import tarfile
from cairn.workbench.store import Store


def backup(root, archive):
    store = Store(root)
    snapshot = root / "workbench.snapshot.db"
    store.backup(snapshot)
    try:
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(snapshot, arcname="workbench.db")
            for name in (
                "projects",
                "identity-key",
                "access-token",
                "provider-auth.enc",
                "network.json",
            ):
                path = root / name
                if path.exists():
                    tar.add(path, arcname=name)
    finally:
        snapshot.unlink(missing_ok=True)


def restore(archive, destination):
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(
            "Restore requires a new empty destination; existing data is never overwritten."
        )
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tar:
        if sum(m.size for m in tar.getmembers()) > 4 * 1024**3:
            raise ValueError("Backup expands beyond the 4 GiB restore limit")
        for member in tar.getmembers():
            target = (destination / member.name).resolve()
            if (
                not target.is_relative_to(destination.resolve())
                or member.issym()
                or member.islnk()
            ):
                raise ValueError("Unsafe archive member")
        tar.extractall(destination, filter="data")
    destination.chmod(0o700)
    for name in ("identity-key", "access-token"):
        if (destination / name).exists():
            (destination / name).chmod(0o600)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("data", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    backup(args.data, args.archive) if args.action == "backup" else restore(
        args.archive, args.data
    )
