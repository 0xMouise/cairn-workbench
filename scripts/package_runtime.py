"""Build the desktop installer's deterministic source runtime resource."""

from pathlib import Path
import tarfile

root = Path(__file__).resolve().parent.parent
destination = root / "web/src-tauri/resources"
destination.mkdir(parents=True, exist_ok=True)
with tarfile.open(destination / "runtime.tar.gz", "w:gz") as archive:
    for folder in ("cairn/src", "scripts"):
        for path in sorted((root / folder).rglob("*")):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and path.suffix != ".pyc"
            ):
                archive.add(
                    path, arcname=str(path.relative_to(root)).replace("\\", "/")
                )
    for name in (
        "cairn/pyproject.toml",
        "cairn/uv.lock",
        "cairn/requirements-workbench.lock",
        "dispatch.local.example.yaml",
        "LICENSE",
    ):
        archive.add(root / name, arcname=name)
print(destination / "runtime.tar.gz")
