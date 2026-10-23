import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from cairn.workbench.app import create_app
from cairn.workbench.store import Store, uid, now, redact
from cairn.workbench.research import allowed, import_requests


class IdleRunner:
    def __init__(self, store):
        self.store, self.active, self.approved = store, {}, []

    def launch(self, ident):
        pass

    def close(self):
        pass

    def cancel(self, ident):
        self.store.state(ident, "cancelled")

    def approve(self, approval, decision):
        self.approved.append((approval["id"], decision))


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path, "test-token", IdleRunner)
    with TestClient(app) as c:
        c.post("/api/v2/login", json={"token": "test-token"})
        yield c


def new_project(client, **kwargs):
    r = client.post(
        "/api/v2/projects",
        json={
            "title": "测试项目",
            "origin": "本地测试",
            "goal": "验证审批",
            "scope": ["http://127.0.0.1:19876"],
            **kwargs,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_auth_and_cross_origin(tmp_path):
    with TestClient(create_app(tmp_path, "token", IdleRunner)) as c:
        assert c.get("/api/v2/overview").status_code == 401
        assert (
            c.post(
                "/api/v2/login",
                json={"token": "token"},
                headers={"Origin": "https://evil.example"},
            ).status_code
            == 403
        )
        assert c.get("/api/v2/health").status_code == 200
        assert c.post("/api/v2/login", json={"token": "bad"}).status_code == 401
        assert c.post("/api/v2/login", json={"token": "token"}).status_code == 200
        assert c.get("/api/v2/overview").status_code == 200
        assert (
            c.get("/api/v2/overview", headers={"Host": "evil.example"}).status_code
            == 400
        )


def test_run_cancel_and_terminal_monotonicity(client):
    pid = new_project(client)
    run = client.post(
        f"/api/v2/projects/{pid}/runs", json={"prompt": "只读检查"}
    ).json()
    assert run["status"] == "queued"
    assert client.post(f"/api/v2/runs/{run['id']}/stop").json()["status"] == "cancelled"
    client.app.state.store.state(run["id"], "completed")
    assert (
        client.get(f"/api/v2/projects/{pid}").json()["runs"][0]["status"] == "cancelled"
    )
    events = client.get("/api/v2/events", params={"project_id": pid}).json()
    assert events and events == sorted(events, key=lambda e: e["seq"])
    cursor = events[-1]["seq"]
    assert client.get("/api/v2/events", params={"after": cursor}).json() == []


def test_reject_approval_and_duplicate_prevention(client):
    pid = new_project(client)
    rid = client.post(f"/api/v2/projects/{pid}/runs", json={"prompt": "任务"}).json()[
        "id"
    ]
    aid = uid("approval")
    client.app.state.store.execute(
        "INSERT INTO wb_approvals(id,run_id,remote_id,permission,details,created_at) VALUES(?,?,?,?,?,?)",
        (aid, rid, "per_test", "shell", "{}", now()),
    )
    assert (
        client.post(f"/api/v2/approvals/{aid}", json={"decision": "reject"}).status_code
        == 200
    )
    assert (
        client.post(f"/api/v2/approvals/{aid}", json={"decision": "once"}).status_code
        == 409
    )
    assert client.app.state.runner.approved == [(aid, "reject")]


def test_evidence_integrity_and_report_escape(client):
    pid = new_project(client)
    other = new_project(client)
    artifact = client.post(
        f"/api/v2/projects/{pid}/artifacts",
        json={
            "name": "../../evidence.txt",
            "content": base64.b64encode(b"evidence").decode(),
        },
    ).json()
    assert artifact["name"] == "evidence.txt"
    body = {
        "title": "<script>alert(1)</script>",
        "status": "confirmed",
        "reproduction": "Step 1",
        "description": "Authorization: Bearer abcdefghijk",
        "evidence": [artifact["id"]],
    }
    assert (
        client.post(f"/api/v2/projects/{other}/findings", json=body).status_code == 400
    )
    assert client.post(f"/api/v2/projects/{pid}/findings", json=body).status_code == 201
    exported = client.get(f"/api/v2/projects/{pid}/report?format=html")
    assert "<script>" not in exported.text and "&lt;script&gt;" in exported.text
    assert "abcdefghijk" not in exported.text
    pdf = client.get(f"/api/v2/projects/{pid}/report?format=pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert client.get(f"/api/v2/artifacts/{artifact['id']}").content == b"evidence"
    assert client.post("/api/v2/backup").status_code == 200


def test_import_scope_and_replay_approval(client):
    pid = new_project(client)
    content = {
        "openapi": "3.0.0",
        "servers": [{"url": "http://127.0.0.1:19876"}],
        "paths": {"/api": {"get": {}}},
    }
    assert (
        client.post(
            f"/api/v2/projects/{pid}/import",
            json={"format": "openapi", "content": content},
        ).json()["count"]
        == 1
    )
    item = client.get(f"/api/v2/projects/{pid}").json()["requests"][0]
    response = client.post(f"/api/v2/requests/{item['id']}/replay")
    assert response.status_code == 200
    approval_id = response.json()["approval_id"]
    assert (
        client.post(
            f"/api/v2/approvals/{approval_id}", json={"decision": "reject"}
        ).status_code
        == 200
    )
    assert (
        client.get(f"/api/v2/projects/{pid}").json()["requests"][0]["response"] is None
    )
    outside = client.post(
        f"/api/v2/projects/{pid}/requests", json={"url": "https://example.com/api"}
    ).json()["id"]
    assert client.post(f"/api/v2/requests/{outside}/replay").status_code == 403


def test_recovery_expires_pending_approvals(client):
    pid = new_project(client)
    run = client.post(f"/api/v2/projects/{pid}/runs", json={"prompt": "任务"}).json()
    client.app.state.store.recover()
    assert (
        client.get(f"/api/v2/projects/{pid}").json()["runs"][0]["status"]
        == "interrupted"
    )


def test_scope_exact_origin_paths_and_redaction():
    scope = ["https://example.com/api"]
    assert allowed("https://example.com/api/user", scope, [])
    assert not allowed("https://example.com/apix", scope, [])
    assert not allowed("https://example.com.evil/api", scope, [])
    assert not allowed("https://example.com:444/api", scope, [])
    assert not allowed(
        "https://example.com/api/admin", scope, ["https://example.com/api/admin"]
    )
    assert json.loads(
        redact({"password": 1234, "nested": {"token": "secret"}, "tokens": 44})
    ) == {"password": "[REDACTED]", "nested": {"token": "[REDACTED]"}, "tokens": 44}
    har = {
        "log": {
            "entries": [
                {
                    "request": {
                        "method": "GET",
                        "url": "https://example.com",
                        "headers": [{"name": "Cookie", "value": "secret"}],
                    }
                }
            ]
        }
    }
    assert not import_requests("har", har)[0]["headers"]
    assert json.loads(
        redact({"X-API-Key": "hidden", "access_token": "hidden", "tokens": 44})
    ) == {"X-API-Key": "[REDACTED]", "access_token": "[REDACTED]", "tokens": 44}


def test_encrypted_identity_never_returned_and_project_bound(client):
    pid = new_project(client)
    other = new_project(client)
    r = client.post(
        f"/api/v2/projects/{pid}/identities",
        json={
            "name": "测试身份",
            "headers": {"Authorization": "Bearer private-test-value"},
        },
    )
    assert r.status_code == 201
    identity_id = r.json()["id"]
    detail = client.get(f"/api/v2/projects/{pid}").text
    assert "private-test-value" not in detail
    row = client.app.state.store.one(
        "SELECT encrypted FROM wb_identities WHERE id=?", (identity_id,)
    )
    assert "private-test-value" not in row["encrypted"]
    assert (
        client.post(
            f"/api/v2/projects/{other}/requests",
            json={"url": "http://127.0.0.1:19876", "identity_id": identity_id},
        ).status_code
        == 400
    )
    assert client.delete("/api/v2/identities/" + identity_id).status_code == 200


def test_actual_http_replay_requires_approval_and_uses_encrypted_identity(client):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading

    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        pid = new_project(client, scope=[url])
        identity = client.post(
            f"/api/v2/projects/{pid}/identities",
            json={
                "name": "Test identity",
                "headers": {"Authorization": "Bearer local-test-only"},
            },
        ).json()["id"]
        qid = client.post(
            f"/api/v2/projects/{pid}/requests",
            json={"url": url + "/health", "identity_id": identity},
        ).json()["id"]
        aid = client.post(f"/api/v2/requests/{qid}/replay").json()["approval_id"]
        assert seen == []
        result = client.post(f"/api/v2/approvals/{aid}", json={"decision": "once"})
        assert result.status_code == 200, result.text
        assert seen == ["Bearer local-test-only"]
        assert (
            client.post(
                f"/api/v2/approvals/{aid}", json={"decision": "once"}
            ).status_code
            == 409
        )
        assert len(seen) == 1
        stored = client.get(f"/api/v2/projects/{pid}").json()["requests"][0]
        assert json.loads(stored["response"])["status"] == 200
        assert "local-test-only" not in client.get(f"/api/v2/projects/{pid}").text
    finally:
        server.shutdown()
        server.server_close()


def test_event_tail_contains_latest_ten_thousand(client):
    pid = new_project(client)
    stamp = now()
    with client.app.state.store.connect() as c:
        c.executemany(
            "INSERT INTO wb_events(project_id,type,data,created_at) VALUES(?,?,?,?)",
            [(pid, "test.event", json.dumps({"n": i}), stamp) for i in range(10010)],
        )
    result = client.get(
        "/api/v2/events", params={"project_id": pid, "tail": True}
    ).json()
    assert (
        len(result) == 10000
        and result[0]["data"]["n"] == 10
        and result[-1]["data"]["n"] == 10009
    )


def test_provider_secret_is_encrypted_and_never_returned(client):
    secret = "test-provider-key-never-a-real-credential"
    invalid = client.put("/api/v2/settings/provider", json={"key": "shortkey"})
    assert invalid.status_code == 422 and "shortkey" not in invalid.text
    response = client.put("/api/v2/settings/provider", json={"key": secret})
    assert response.status_code == 200
    assert secret not in (client.app.state.store.root / "provider-auth.enc").read_text()
    assert secret not in client.get("/api/v2/settings/provider").text
    assert client.get("/api/v2/settings/provider").json()["source"] == "workbench"
    assert client.delete("/api/v2/settings/provider").status_code == 200
