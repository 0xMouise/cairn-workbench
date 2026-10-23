"""Harmless live-model smoke test; no external targets, tools or paid fallback."""

import json
import os
from pathlib import Path
import time
import requests

root = Path(os.environ.get("CAIRN_SMOKE_DATA", ".runtime/dev-data"))
session = requests.Session()
session.trust_env = False
session.headers["Authorization"] = (
    "Bearer " + (root / "access-token").read_text().strip()
)
base = os.environ.get("CAIRN_SMOKE_URL", "http://127.0.0.1:18100") + "/api/v2"
for attempt in range(40):
    try:
        session.get(base + "/health", timeout=2).raise_for_status()
        break
    except requests.RequestException:
        time.sleep(0.25)
else:
    raise SystemExit("Workbench did not become healthy.")
project = session.post(
    base + "/projects",
    json={
        "title": "引擎连通验收 · 本地计算",
        "origin": "本地计算测试，不访问网络目标，不调用工具。",
        "goal": "确认 2+2=4，返回事实与完成依据。",
        "scope": [],
        "excluded": [],
    },
    timeout=10,
).json()
run = session.post(
    base + f"/projects/{project['id']}/runs",
    json={
        "prompt": "仅回答计算结果，禁止工具调用。已知 2+2=4，返回 fact 和 complete JSON 即可。",
        "max_steps": 1,
        "timeout": 60,
    },
    timeout=10,
).json()
print(
    json.dumps({"project_id": project["id"], "run_id": run["id"]}, ensure_ascii=False),
    flush=True,
)
deadline = time.monotonic() + 100
while time.monotonic() < deadline:
    detail = session.get(base + f"/projects/{project['id']}", timeout=10).json()
    state = next(item for item in detail["runs"] if item["id"] == run["id"])
    if state["status"] not in ("queued", "running", "awaiting_approval"):
        print(
            json.dumps(
                {key: state[key] for key in ("status", "error", "cost", "tokens")},
                ensure_ascii=False,
            )
        )
        print("graph_nodes", len(detail["graph"]))
        break
    time.sleep(1)
else:
    session.post(base + f"/runs/{run['id']}/stop", timeout=10)
    raise SystemExit("Live smoke test timed out and was stopped.")
