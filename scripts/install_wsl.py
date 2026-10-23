"""Run inside WSL after copying the repository. No existing Cairn services/data are changed."""

from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent.parent
home = Path.home()
subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)
subprocess.run(
    [
        str(root / ".venv/bin/pip"),
        "install",
        "-r",
        str(root / "cairn/requirements-workbench.lock"),
    ],
    check=True,
)
subprocess.run(
    [str(root / ".venv/bin/pip"), "install", "--no-deps", "-e", str(root / "cairn")],
    check=True,
)
binary = home / "apps/cairn/opencode-runtime/node_modules/.bin/opencode"
if not binary.exists():
    subprocess.run(
        [
            "npm",
            "install",
            "--prefix",
            str(root / "opencode-runtime"),
            "opencode-ai@1.19.0",
        ],
        check=True,
    )
    binary = root / "opencode-runtime/node_modules/.bin/opencode"
data = home / ".local/share/cairn-workbench"
data.mkdir(parents=True, exist_ok=True)
data.chmod(0o700)
unit = home / ".config/systemd/user/cairn-workbench.service"
unit.parent.mkdir(parents=True, exist_ok=True)
unit.write_text(f"""[Unit]
Description=Cairn Workbench local research engine
After=network.target

[Service]
Type=simple
WorkingDirectory={root}
Environment="PATH={binary.parent}:{root}/.venv/bin:{home}/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH={root}/cairn/src"
Environment="CAIRN_OPENCODE_BIN={binary}"
Environment="CAIRN_WORKBENCH_DATA={data}"
Environment="NO_PROXY=127.0.0.1,localhost,::1"
Environment="no_proxy=127.0.0.1,localhost,::1"
ExecStart={root}/.venv/bin/python {root}/scripts/serve_workbench.py
Restart=on-failure
RestartSec=3
KillMode=control-group
TimeoutStopSec=15

[Install]
WantedBy=default.target
""")
subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
subprocess.run(
    ["systemctl", "--user", "enable", "--now", "cairn-workbench.service"], check=True
)
print("Cairn Workbench installed at http://127.0.0.1:18100")
