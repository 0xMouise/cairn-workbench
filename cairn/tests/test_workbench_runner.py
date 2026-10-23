"""Protocol simulation covers runtime control; it is not live-model evidence."""

import json
import threading
import time
from pathlib import Path

import pytest

from cairn.workbench.store import Store, now, uid
from cairn.workbench.runner import Runner


class Reply:
    def __init__(self, data=None, events=None):
        self.data, self.events = data, events

    def json(self):
        return self.data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_lines(self, **kwargs):
        yield from self.events()


class ProtocolBackend:
    instances = []
    quota = False

    def __init__(self, store, project_id):
        self.reply = None
        self.signal = threading.Event()
        self.closed = False
        self.executions = 0
        self.messages = 0
        self.instances.append(self)

    def start(self):
        pass

    def stop(self):
        self.closed = True
        self.signal.set()

    def request(self, method, path, **kwargs):
        if path == "/session":
            return Reply({"id": "ses_fixture"})
        if path == "/event":

            def events():
                if not self.quota:
                    yield "data: " + json.dumps(
                        {
                            "type": "permission.asked",
                            "properties": {
                                "sessionID": "ses_fixture",
                                "id": "per_fixture",
                                "permission": "shell",
                                "patterns": ["echo test"],
                                "metadata": {"command": "echo test"},
                            },
                        }
                    )
                while not self.closed:
                    time.sleep(0.02)

            return Reply(events=events)
        if path == "/permission":
            return Reply(
                []
                if self.quota or self.reply
                else [
                    {
                        "sessionID": "ses_fixture",
                        "id": "per_fixture",
                        "permission": "shell",
                        "patterns": ["echo test"],
                        "metadata": {"command": "echo test"},
                    }
                ]
            )
        if path == "/session/status":
            return Reply(
                {
                    "ses_fixture": {
                        "type": "retry",
                        "message": "Free usage limit reached",
                    }
                }
                if self.quota
                else {}
            )
        if path.endswith("/reply"):
            self.reply = kwargs["json"]["reply"]
            self.signal.set()
            return Reply(True)
        if path.endswith("/abort"):
            self.signal.set()
            return Reply(True)
        if path.endswith("/message"):
            if self.messages == 0 or self.reply is None:
                return Reply([])
            if self.reply == "once":
                self.executions = 1
                return Reply(
                    [
                        {
                            "info": {
                                "id": "msg_fixture",
                                "role": "assistant",
                                "time": {"completed": 1},
                                "cost": 0,
                                "tokens": {"total": 20},
                            },
                            "parts": [
                                {
                                    "type": "text",
                                    "text": json.dumps(
                                        {
                                            "accepted": True,
                                            "data": {
                                                "fact": {
                                                    "description": "CI simulated local fact"
                                                },
                                                "complete": {
                                                    "description": "CI simulated goal satisfied"
                                                },
                                            },
                                        }
                                    ),
                                }
                            ],
                        }
                    ]
                )
            return Reply(
                [
                    {
                        "info": {
                            "id": "msg_fixture",
                            "role": "assistant",
                            "error": {"message": "Denied or aborted"},
                        },
                        "parts": [],
                    }
                ]
            )
        if path.endswith("/prompt_async"):
            self.messages += 1
            assert kwargs["json"]["model"]["modelID"] == "deepseek-v4.1-flash-free"
            assert kwargs["json"]["variant"] == "low"
            return Reply(None)
        raise AssertionError((method, path))


def wait_until(fn):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(0.03)
    raise AssertionError("condition did not become true")


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    ProtocolBackend.instances = []
    ProtocolBackend.quota = False
    monkeypatch.setattr("cairn.workbench.runner.OpenCode", ProtocolBackend)
    store = Store(tmp_path)
    pid = uid("project")
    rid = uid("run")
    stamp = now()
    store.execute(
        "INSERT INTO wb_projects(id,title,origin,goal,created_at,updated_at) VALUES(?,?,?,?,?,?)",
        (pid, "Protocol CI fixture", "local", "verify", stamp, stamp),
    )
    store.execute(
        "INSERT INTO wb_runs(id,project_id,prompt,status,model,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (
            rid,
            pid,
            "CI simulated task",
            "queued",
            "opencode/deepseek-v4.1-flash-free",
            stamp,
            stamp,
        ),
    )
    runner = Runner(store)
    yield store, runner, rid
    runner.close()


@pytest.mark.parametrize("decision", ["once", "reject"])
def test_protocol_approval_controls_execution(runtime, decision):
    store, runner, rid = runtime
    runner.launch(rid)
    approval = wait_until(
        lambda: store.one("SELECT * FROM wb_approvals WHERE status='pending'")
    )
    backend = ProtocolBackend.instances[0]
    assert backend.executions == 0
    runner.approve(approval, decision)
    wait_until(
        lambda: (
            store.one("SELECT status FROM wb_runs WHERE id=?", (rid,))["status"]
            in ("completed", "failed")
        )
    )
    assert backend.executions == (1 if decision == "once" else 0)
    if decision == "once":
        assert (
            store.one("SELECT status FROM wb_runs WHERE id=?", (rid,))["status"]
            == "completed"
        )
        assert store.one("SELECT * FROM wb_graph WHERE kind='complete'")


def test_protocol_quota_stops_hidden_retries(runtime):
    ProtocolBackend.quota = True
    store, runner, rid = runtime
    runner.launch(rid)
    wait_until(
        lambda: (
            store.one("SELECT status FROM wb_runs WHERE id=?", (rid,))["status"]
            == "quota_blocked"
        )
    )
    wait_until(lambda: ProtocolBackend.instances[0].closed)
    assert ProtocolBackend.instances[0].messages == 1
    assert ProtocolBackend.instances[0].executions == 0


def test_protocol_cancel_pending_tool(runtime):
    store, runner, rid = runtime
    runner.launch(rid)
    wait_until(lambda: store.one("SELECT * FROM wb_approvals WHERE status='pending'"))
    runner.cancel(rid)
    wait_until(lambda: ProtocolBackend.instances[0].closed)
    assert ProtocolBackend.instances[0].executions == 0
    assert (
        store.one("SELECT status FROM wb_runs WHERE id=?", (rid,))["status"]
        == "cancelled"
    )
    assert not store.one("SELECT * FROM wb_approvals WHERE status='pending'")


@pytest.mark.parametrize("invalid_source", [False, True])
def test_bounded_bootstrap_reason_explore_loop(runtime, monkeypatch, invalid_source):
    """Mock model output; exercises the actual Cairn contract/orchestration path."""
    ProtocolBackend.quota = True  # This test does not simulate permission events.
    store, runner, rid = runtime
    calls = []

    def turn(backend, run, prompt):
        calls.append(prompt)
        fact = store.one(
            "SELECT id FROM wb_graph WHERE kind='fact' ORDER BY created_at DESC LIMIT 1"
        )
        if len(calls) == 1:
            payload = {"fact": {"description": "partial local fact"}}
        elif len(calls) == 2:
            payload = {
                "intents": [
                    {
                        "from": ["invalid"] if invalid_source else [fact["id"]],
                        "description": "one local exploration",
                    }
                ]
            }
        elif len(calls) == 3:
            payload = {"description": "confirmed exploration result"}
        else:
            payload = {
                "complete": {
                    "from": [fact["id"]],
                    "description": "goal satisfied by confirmed facts",
                }
            }
        return json.dumps({"accepted": True, "data": payload})

    monkeypatch.setattr(runner, "_turn", turn)
    runner.launch(rid)
    wait_until(
        lambda: (
            store.one("SELECT status FROM wb_runs WHERE id=?", (rid,))["status"]
            in ("completed", "failed")
        )
    )
    state = store.one("SELECT status FROM wb_runs WHERE id=?", (rid,))["status"]
    assert state == ("failed" if invalid_source else "completed")
    if not invalid_source:
        assert len(calls) == 4
        assert [
            r["kind"]
            for r in store.all("SELECT kind FROM wb_graph ORDER BY created_at")
        ] == ["fact", "intent", "fact", "complete"]
    else:
        assert len(calls) == 2 and not store.one(
            "SELECT * FROM wb_graph WHERE kind='intent'"
        )
