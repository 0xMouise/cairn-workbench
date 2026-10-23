from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import (
    ProjectInput,
    RunInput,
    FindingInput,
    ApprovalInput,
    HintInput,
    ImportInput,
    RequestInput,
    LoginInput,
    IdentityInput,
    NetworkInput,
    ProviderInput,
)
from .vault import Vault
from .research import (
    import_requests,
    allowed,
    replay_request,
    report,
    html_report,
    pdf_report,
)
from .runner import Runner, MODEL, TERMINAL
from .store import Store, uid, now, redact


def create_app(
    root: Path | None = None, token: str | None = None, runner_factory=Runner
):
    store = Store(
        root
        or Path(
            os.environ.get(
                "CAIRN_WORKBENCH_DATA",
                str(Path.home() / ".local/share/cairn-workbench"),
            )
        )
    )
    secret_path = store.root / "access-token"
    if token is None:
        if not secret_path.exists():
            secret_path.write_text(secrets.token_urlsafe(40))
            secret_path.chmod(0o600)
        token = secret_path.read_text().strip()
    runner = runner_factory(store)
    vault = Vault(store.root)

    @asynccontextmanager
    async def lifespan(app):
        store.recover()
        yield
        runner.close()

    app = FastAPI(
        title="Cairn Workbench",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.state.store, app.state.runner = store, runner

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(
            {
                "detail": [
                    {
                        "loc": list(error["loc"]),
                        "msg": error["msg"],
                        "type": error["type"],
                    }
                    for error in exc.errors()
                ]
            },
            status_code=422,
        )

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"],
    )

    @app.middleware("http")
    async def local_auth(request, call_next):
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).netloc != request.headers.get("host"):
            return JSONResponse({"detail": "不允许跨来源访问本地服务"}, status_code=403)
        if int(request.headers.get("content-length", "0") or 0) > 12 * 1024 * 1024:
            return JSONResponse({"detail": "上传大小超过限制"}, status_code=413)
        path = request.url.path
        if path.startswith("/api/") or path == "/openapi.json":
            if path not in ("/api/v2/login", "/api/v2/health"):
                supplied = request.headers.get("authorization", "").removeprefix(
                    "Bearer "
                ) or request.cookies.get("cairn_session", "")
                if not hmac.compare_digest(supplied, token):
                    return JSONResponse(
                        {"detail": "请使用本机启动入口登录"}, status_code=401
                    )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        )
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def project(pid):
        item = store.one("SELECT * FROM wb_projects WHERE id=?", (pid,))
        if not item:
            raise HTTPException(404, "项目不存在")
        return item

    def run_item(rid):
        item = store.one("SELECT * FROM wb_runs WHERE id=?", (rid,))
        if not item:
            raise HTTPException(404, "任务不存在")
        return item

    @app.get("/api/v2/health")
    def health():
        return {"healthy": True, "version": "0.1.0"}

    @app.post("/api/v2/login")
    def login(body: LoginInput, response: Response):
        if not hmac.compare_digest(body.token, token):
            raise HTTPException(401, "本机访问令牌无效")
        response.set_cookie(
            "cairn_session",
            token,
            httponly=True,
            samesite="strict",
            max_age=86400,
            path="/",
        )
        return {"ok": True}

    @app.post("/api/v2/logout")
    def logout(response: Response):
        response.delete_cookie("cairn_session", path="/")
        return {"ok": True}

    @app.get("/api/v2/overview")
    def overview():
        return {
            "projects": store.all("SELECT * FROM wb_projects ORDER BY updated_at DESC"),
            "runs": store.all(
                "SELECT * FROM wb_runs ORDER BY created_at DESC LIMIT 200"
            ),
            "approvals": store.all(
                "SELECT a.*,r.project_id FROM wb_approvals a JOIN wb_runs r ON r.id=a.run_id WHERE a.status='pending' ORDER BY a.created_at"
            ),
            "cursor": store.one("SELECT COALESCE(MAX(seq),0) AS seq FROM wb_events")[
                "seq"
            ],
            "model": MODEL,
        }

    @app.post("/api/v2/projects", status_code=201)
    def create_project(body: ProjectInput):
        pid, stamp = uid("project"), now()
        with store.connect() as c:
            c.execute(
                "INSERT INTO wb_projects(id,title,origin,goal,scope,excluded,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (
                    pid,
                    body.title,
                    body.origin,
                    body.goal,
                    json.dumps(body.scope),
                    json.dumps(body.excluded),
                    stamp,
                    stamp,
                ),
            )
            for kind, description in [("origin", body.origin), ("goal", body.goal)]:
                c.execute(
                    "INSERT INTO wb_graph VALUES(?,?,?,?,?,?,?)",
                    (uid("node"), pid, None, kind, description, "[]", stamp),
                )
            store.event(pid, None, "project.created", {"title": body.title}, c)
        store.project_dir(pid)
        return project(pid)

    @app.get("/api/v2/projects/{pid}")
    def detail(pid: str):
        p = project(pid)
        return {
            "project": p,
            "runs": store.all(
                "SELECT * FROM wb_runs WHERE project_id=? ORDER BY created_at", (pid,)
            ),
            "findings": store.all(
                "SELECT * FROM wb_findings WHERE project_id=? ORDER BY created_at DESC",
                (pid,),
            ),
            "artifacts": store.all(
                "SELECT id,project_id,run_id,name,media_type,size,sha256,created_at FROM wb_artifacts WHERE project_id=? ORDER BY created_at DESC",
                (pid,),
            ),
            "requests": store.all(
                "SELECT * FROM wb_requests WHERE project_id=? ORDER BY created_at",
                (pid,),
            ),
            "graph": store.all(
                "SELECT * FROM wb_graph WHERE project_id=? ORDER BY created_at", (pid,)
            ),
            "hints": store.all(
                "SELECT * FROM wb_hints WHERE project_id=? ORDER BY created_at", (pid,)
            ),
            "identities": store.all(
                "SELECT id,name,header_names,created_at FROM wb_identities WHERE project_id=? ORDER BY created_at",
                (pid,),
            ),
        }

    @app.patch("/api/v2/projects/{pid}")
    def edit_project(pid: str, body: ProjectInput):
        project(pid)
        store.execute(
            "UPDATE wb_projects SET title=?,origin=?,goal=?,scope=?,excluded=?,updated_at=? WHERE id=?",
            (
                body.title,
                body.origin,
                body.goal,
                json.dumps(body.scope),
                json.dumps(body.excluded),
                now(),
                pid,
            ),
        )
        store.event(pid, None, "project.updated", {"title": body.title})
        return project(pid)

    @app.post("/api/v2/projects/{pid}/archive")
    def archive(pid: str):
        p = project(pid)
        if store.one(
            "SELECT id FROM wb_runs WHERE project_id=? AND status IN ('running','queued','awaiting_approval')",
            (pid,),
        ):
            raise HTTPException(409, "请先停止此项目中的活动任务")
        store.execute(
            "UPDATE wb_projects SET archived=?,updated_at=? WHERE id=?",
            (not p["archived"], now(), pid),
        )
        store.event(pid, None, "project.archived", {"archived": not p["archived"]})
        return project(pid)

    @app.post("/api/v2/projects/{pid}/runs", status_code=201)
    def create_run(pid: str, body: RunInput):
        p = project(pid)
        if p["archived"]:
            raise HTTPException(409, "请先恢复已归档项目")
        if body.parent_id:
            parent = run_item(body.parent_id)
            if parent["project_id"] != pid or parent["status"] not in TERMINAL:
                raise HTTPException(409, "只能从同项目已结束任务创建新尝试")
        rid, stamp = uid("run"), now()
        with store.connect() as c:
            c.execute(
                "INSERT INTO wb_runs(id,project_id,prompt,status,parent_id,model,created_at,updated_at,max_steps,timeout) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    rid,
                    pid,
                    body.prompt,
                    "queued",
                    body.parent_id,
                    MODEL,
                    stamp,
                    stamp,
                    body.max_steps,
                    body.timeout,
                ),
            )
            c.execute("UPDATE wb_projects SET updated_at=? WHERE id=?", (stamp, pid))
            store.event(
                pid,
                rid,
                "run.created",
                {"prompt": body.prompt, "parent_id": body.parent_id},
                c,
            )
        runner.launch(rid)
        return run_item(rid)

    @app.post("/api/v2/runs/{rid}/stop")
    def stop(rid: str):
        run = run_item(rid)
        if run["status"] not in TERMINAL:
            runner.cancel(rid)
        return run_item(rid)

    @app.post("/api/v2/projects/{pid}/hints", status_code=201)
    def hint(pid: str, body: HintInput):
        project(pid)
        if body.run_id and run_item(body.run_id)["project_id"] != pid:
            raise HTTPException(400, "任务不属于此项目")
        ident = uid("hint")
        with store.connect() as c:
            c.execute(
                "INSERT INTO wb_hints VALUES(?,?,?,?,?)",
                (ident, pid, body.run_id, body.content, now()),
            )
            store.event(pid, body.run_id, "hint.added", {"content": body.content}, c)
        return {"id": ident, "applies": "下一个探索决策阶段"}

    @app.get("/api/v2/events")
    async def events(
        request: Request,
        project_id: str | None = None,
        after: int = 0,
        stream: bool = False,
        tail: bool = False,
    ):
        if project_id:
            project(project_id)
        cursor = max(after, int(request.headers.get("last-event-id", "0") or 0))

        def batch(since):
            args = (since, project_id) if project_id else (since,)
            rows = store.all(
                "SELECT * FROM wb_events WHERE seq>? "
                + ("AND project_id=? " if project_id else "")
                + "ORDER BY seq LIMIT 500",
                args,
            )
            for row in rows:
                row["data"] = json.loads(row["data"])
            return rows

        if not stream:
            if tail:
                args = (project_id,) if project_id else ()
                rows = store.all(
                    "SELECT * FROM wb_events "
                    + ("WHERE project_id=? " if project_id else "")
                    + "ORDER BY seq DESC LIMIT 10000",
                    args,
                )
                for row in rows:
                    row["data"] = json.loads(row["data"])
                return list(reversed(rows))
            return batch(cursor)

        async def generate():
            nonlocal cursor
            heartbeat = 0
            while not await request.is_disconnected():
                rows = await asyncio.to_thread(batch, cursor)
                for row in rows:
                    cursor = row["seq"]
                    yield f"id: {cursor}\ndata: {json.dumps(row, ensure_ascii=False)}\n\n"
                heartbeat += 1
                if heartbeat % 20 == 0:
                    yield ": heartbeat\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no"},
        )

    @app.post("/api/v2/approvals/{aid}")
    def approve(aid: str, body: ApprovalInput):
        with store.connect() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM wb_approvals WHERE id=?", (aid,)).fetchone()
            if not row:
                raise HTTPException(404, "审批不存在")
            approval = dict(row)
            if approval["status"] != "pending":
                raise HTTPException(409, "审批已处理或已失效")
            c.execute(
                "UPDATE wb_approvals SET status='processing' WHERE id=? AND status='pending'",
                (aid,),
            )
        run = run_item(approval["run_id"])
        try:
            if approval["remote_id"].startswith("request:"):
                if body.decision == "once":
                    request_id = approval["remote_id"].split(":", 1)[1]
                    item = store.one(
                        "SELECT * FROM wb_requests WHERE id=? AND project_id=?",
                        (request_id, run["project_id"]),
                    )
                    p = project(run["project_id"])
                    if not item or not allowed(
                        item["url"], json.loads(p["scope"]), json.loads(p["excluded"])
                    ):
                        raise ValueError("请求已不在项目允许范围内")
                    if item.get("identity_id"):
                        identity = store.one(
                            "SELECT * FROM wb_identities WHERE id=? AND project_id=?",
                            (item["identity_id"], run["project_id"]),
                        )
                        if not identity:
                            raise ValueError("关联身份已删除")
                        item["headers"] = {
                            **json.loads(item["headers"]),
                            **vault.decrypt(identity["encrypted"]),
                        }
                    result = replay_request(item)
                    store.execute(
                        "UPDATE wb_requests SET response=? WHERE id=?",
                        (redact(result), item["id"]),
                    )
                    store.event(
                        run["project_id"],
                        run["id"],
                        "request.response",
                        {"request_id": item["id"], **result},
                    )
                store.state(
                    run["id"], "completed" if body.decision == "once" else "cancelled"
                )
            else:
                if run["status"] in TERMINAL:
                    raise RuntimeError("执行任务已结束")
                runner.approve(approval, body.decision)
                store.state(run["id"], "running")
        except Exception as exc:
            store.execute(
                "UPDATE wb_approvals SET status='expired',resolved_at=? WHERE id=?",
                (now(), aid),
            )
            if approval["remote_id"].startswith("request:"):
                store.state(run["id"], "failed", str(exc))
            raise HTTPException(409, redact(str(exc))) from exc
        store.execute(
            "UPDATE wb_approvals SET status=?,resolved_at=? WHERE id=?",
            ("approved" if body.decision == "once" else "rejected", now(), aid),
        )
        store.event(
            run["project_id"],
            run["id"],
            "approval.resolved",
            {"id": aid, "decision": body.decision},
        )
        return {"ok": True}

    def validate_evidence(pid, body):
        if body.run_id and run_item(body.run_id)["project_id"] != pid:
            raise HTTPException(400, "运行不属于此项目")
        for ident in body.evidence:
            if not store.one(
                "SELECT id FROM wb_artifacts WHERE id=? AND project_id=?", (ident, pid)
            ):
                raise HTTPException(400, "证据不存在或不属于此项目")
        if body.status == "confirmed" and (
            not body.evidence or not body.reproduction.strip()
        ):
            raise HTTPException(400, "确认发现前需要关联证据并填写复现步骤")

    @app.post("/api/v2/projects/{pid}/findings", status_code=201)
    def create_finding(pid: str, body: FindingInput):
        project(pid)
        validate_evidence(pid, body)
        ident, stamp = uid("finding"), now()
        store.execute(
            "INSERT INTO wb_findings VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                ident,
                pid,
                body.run_id,
                body.title,
                body.severity,
                body.status,
                body.description,
                body.reproduction,
                body.impact,
                json.dumps(body.evidence),
                stamp,
                stamp,
            ),
        )
        store.event(
            pid, body.run_id, "finding.created", {"id": ident, "title": body.title}
        )
        return store.one("SELECT * FROM wb_findings WHERE id=?", (ident,))

    @app.put("/api/v2/findings/{fid}")
    def edit_finding(fid: str, body: FindingInput):
        item = store.one("SELECT * FROM wb_findings WHERE id=?", (fid,))
        if not item:
            raise HTTPException(404, "发现不存在")
        validate_evidence(item["project_id"], body)
        store.execute(
            "UPDATE wb_findings SET title=?,severity=?,status=?,description=?,reproduction=?,impact=?,evidence=?,run_id=?,updated_at=? WHERE id=?",
            (
                body.title,
                body.severity,
                body.status,
                body.description,
                body.reproduction,
                body.impact,
                json.dumps(body.evidence),
                body.run_id,
                now(),
                fid,
            ),
        )
        store.event(
            item["project_id"],
            body.run_id,
            "finding.updated",
            {"id": fid, "status": body.status},
        )
        return store.one("SELECT * FROM wb_findings WHERE id=?", (fid,))

    @app.post("/api/v2/projects/{pid}/artifacts", status_code=201)
    async def upload(pid: str, request: Request):
        project(pid)
        body = await request.json()
        try:
            content = base64.b64decode(body.get("content", ""), validate=True)
        except ValueError as exc:
            raise HTTPException(400, "附件编码无效") from exc
        if len(content) > 8 * 1024 * 1024:
            raise HTTPException(413, "单个附件最大 8 MiB")
        name = (
            str(body.get("name", "attachment")).replace("\\", "/").split("/")[-1][:200]
        )
        if not name or name in (".", ".."):
            raise HTTPException(400, "文件名无效")
        rid = body.get("run_id")
        if rid and run_item(rid)["project_id"] != pid:
            raise HTTPException(400, "运行不属于此项目")
        ident = uid("artifact")
        folder = store.project_dir(pid) / "artifacts"
        folder.mkdir(exist_ok=True)
        path = folder / ident
        path.write_bytes(content)
        store.execute(
            "INSERT INTO wb_artifacts VALUES(?,?,?,?,?,?,?,?,?)",
            (
                ident,
                pid,
                rid,
                name,
                str(path.relative_to(store.root)),
                body.get("media_type", "application/octet-stream"),
                len(content),
                hashlib.sha256(content).hexdigest(),
                now(),
            ),
        )
        store.event(pid, rid, "artifact.added", {"id": ident, "name": name})
        return {"id": ident, "name": name}

    @app.get("/api/v2/artifacts/{aid}")
    def download(aid: str):
        item = store.one("SELECT * FROM wb_artifacts WHERE id=?", (aid,))
        if not item:
            raise HTTPException(404, "附件不存在")
        path = (store.root / item["path"]).resolve()
        if not path.is_relative_to(store.root) or not path.is_file():
            raise HTTPException(404, "附件文件不可用")
        return FileResponse(
            path, filename=item["name"], media_type="application/octet-stream"
        )

    @app.post("/api/v2/projects/{pid}/requests", status_code=201)
    def add_request(pid: str, body: RequestInput):
        p = project(pid)
        try:
            in_scope = allowed(
                body.url, json.loads(p["scope"]), json.loads(p["excluded"])
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        ident = uid("request")
        if body.identity_id and not store.one(
            "SELECT id FROM wb_identities WHERE id=? AND project_id=?",
            (body.identity_id, pid),
        ):
            raise HTTPException(400, "身份不属于此项目")
        store.execute(
            "INSERT INTO wb_requests(id,project_id,method,url,headers,body,created_at,identity_id) VALUES(?,?,?,?,?,?,?,?)",
            (
                ident,
                pid,
                body.method,
                body.url,
                redact(body.headers),
                redact(body.body),
                now(),
                body.identity_id,
            ),
        )
        store.event(pid, None, "request.added", {"id": ident, "in_scope": in_scope})
        return {"id": ident, "in_scope": in_scope}

    @app.post("/api/v2/projects/{pid}/identities", status_code=201)
    def create_identity(pid: str, body: IdentityInput):
        project(pid)
        if any(
            "\r" in k or "\n" in k or "\r" in v or "\n" in v
            for k, v in body.headers.items()
        ):
            raise HTTPException(400, "请求头不能包含换行")
        ident = uid("identity")
        store.execute(
            "INSERT INTO wb_identities VALUES(?,?,?,?,?,?)",
            (
                ident,
                pid,
                body.name,
                vault.encrypt(body.headers),
                json.dumps(list(body.headers)),
                now(),
            ),
        )
        store.event(pid, None, "identity.created", {"id": ident, "name": body.name})
        return {"id": ident, "name": body.name, "header_names": list(body.headers)}

    @app.delete("/api/v2/identities/{identity_id}")
    def delete_identity(identity_id: str):
        identity = store.one("SELECT * FROM wb_identities WHERE id=?", (identity_id,))
        if not identity:
            raise HTTPException(404, "身份不存在")
        store.execute("DELETE FROM wb_identities WHERE id=?", (identity_id,))
        store.event(
            identity["project_id"], None, "identity.deleted", {"id": identity_id}
        )
        return {"ok": True}

    @app.post("/api/v2/projects/{pid}/import")
    def import_api(pid: str, body: ImportInput):
        project(pid)
        try:
            items = import_requests(body.format, body.content)
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            raise HTTPException(400, "导入失败：" + str(exc)) from exc
        for item in items:
            add_request(pid, RequestInput(**item))
        return {"count": len(items)}

    @app.post("/api/v2/requests/{qid}/replay")
    def replay(qid: str):
        item = store.one("SELECT * FROM wb_requests WHERE id=?", (qid,))
        if not item:
            raise HTTPException(404, "请求不存在")
        p = project(item["project_id"])
        if not allowed(item["url"], json.loads(p["scope"]), json.loads(p["excluded"])):
            raise HTTPException(403, "请求不在允许范围内或命中排除项")
        rid, aid, stamp = uid("run"), uid("approval"), now()
        with store.connect() as c:
            c.execute(
                "INSERT INTO wb_runs(id,project_id,prompt,status,model,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                (
                    rid,
                    p["id"],
                    f"重放 {item['method']} {item['url']}",
                    "awaiting_approval",
                    MODEL,
                    stamp,
                    stamp,
                ),
            )
            c.execute(
                "INSERT INTO wb_approvals(id,run_id,remote_id,permission,details,created_at) VALUES(?,?,?,?,?,?)",
                (
                    aid,
                    rid,
                    "request:" + qid,
                    "http_request",
                    redact(
                        {
                            "method": item["method"],
                            "url": item["url"],
                            "body": item["body"],
                        }
                    ),
                    stamp,
                ),
            )
            store.event(
                p["id"],
                rid,
                "approval.requested",
                {"id": aid, "permission": "http_request", "url": item["url"]},
                c,
            )
        return {"run_id": rid, "approval_id": aid}

    @app.get("/api/v2/projects/{pid}/report")
    def export_report(pid: str, format: str = "markdown"):
        p = project(pid)
        content = report(
            p,
            store.all("SELECT * FROM wb_findings WHERE project_id=?", (pid,)),
            store.all("SELECT * FROM wb_artifacts WHERE project_id=?", (pid,)),
        )
        if format == "html":
            return Response(
                html_report(content),
                media_type="text/html",
                headers={
                    "Content-Disposition": 'attachment; filename="cairn-report.html"'
                },
            )
        if format == "pdf":
            return Response(
                pdf_report(content),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": 'attachment; filename="cairn-report.pdf"'
                },
            )
        if format != "markdown":
            raise HTTPException(400, "支持 markdown、html 或 pdf")
        return Response(
            content,
            media_type="text/markdown",
            headers={"Content-Disposition": 'attachment; filename="cairn-report.md"'},
        )

    @app.get("/api/v2/diagnostics")
    def diagnostics():
        return {
            "version": "0.1.0",
            "platform": os.name,
            "model": MODEL,
            "opencode_available": bool(
                os.environ.get("CAIRN_OPENCODE_BIN")
                or shutil.which("opencode")
                or shutil.which("opencode.cmd")
            ),
            "active_runs": len(runner.active),
            "database": "SQLite / WAL",
            "schema_version": 2,
            "execution": "WSL Kali / 当前用户权限"
            if os.name != "nt"
            else "Windows / 当前用户权限",
            "approval": "显式确认 · 不自动批准 · 当前运行后端支持审批",
            "paid_fallback": False,
        }

    @app.get("/api/v2/settings/provider")
    def get_provider():
        configured = (store.root / "provider-auth.enc").exists()
        source = Path(
            os.environ.get(
                "CAIRN_OPENCODE_AUTH",
                str(Path.home() / ".local/share/opencode/auth.json"),
            )
        )
        return {
            "configured": configured or source.is_file(),
            "source": "workbench"
            if configured
            else "existing-opencode"
            if source.is_file()
            else "not-configured",
            "model": MODEL,
        }

    @app.put("/api/v2/settings/provider")
    def set_provider(body: ProviderInput):
        if any(char in body.key for char in ("\r", "\n", "\x00")):
            raise HTTPException(400, "API Key 格式无效")
        path = store.root / "provider-auth.enc"
        path.write_text(vault.encrypt({"opencode": {"type": "api", "key": body.key}}))
        path.chmod(0o600)
        store.event(None, None, "settings.provider", {"configured": True})
        return {"ok": True}

    @app.delete("/api/v2/settings/provider")
    def clear_provider():
        (store.root / "provider-auth.enc").unlink(missing_ok=True)
        store.event(None, None, "settings.provider", {"configured": False})
        return {"ok": True}

    @app.get("/api/v2/settings/network")
    def get_network():
        path = store.root / "network.json"
        return json.loads(path.read_text()) if path.exists() else {"proxy": ""}

    @app.put("/api/v2/settings/network")
    def set_network(body: NetworkInput):
        if body.proxy:
            parsed = urlsplit(body.proxy)
            if (
                parsed.scheme not in ("http", "https")
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise HTTPException(
                    400, "代理需要 HTTP/HTTPS URL，且不能包含凭据、查询或片段"
                )
        path = store.root / "network.json"
        path.write_text(json.dumps({"proxy": body.proxy}))
        path.chmod(0o600)
        store.event(
            None, None, "settings.network", {"proxy_configured": bool(body.proxy)}
        )
        return {"ok": True, "applies": "新启动的执行会话"}

    @app.get("/api/v2/diagnostics/export")
    def diagnostic_export():
        return JSONResponse(
            {
                "diagnostics": diagnostics(),
                "runs": [
                    {k: r[k] for k in ("id", "status", "created_at", "error")}
                    for r in store.all(
                        "SELECT * FROM wb_runs ORDER BY created_at DESC LIMIT 20"
                    )
                ],
            },
            headers={
                "Content-Disposition": 'attachment; filename="cairn-diagnostics.json"'
            },
        )

    @app.post("/api/v2/backup")
    def backup():
        folder = store.root / "backups"
        folder.mkdir(exist_ok=True)
        target = folder / (uid("backup") + ".db")
        store.backup(target)
        return {"name": target.name, "includes": "数据库；证据文件请一并备份项目目录"}

    @app.websocket("/api/v2/projects/{pid}/terminal")
    async def terminal(websocket: WebSocket, pid: str):
        from .terminal import terminal_socket

        if not hmac.compare_digest(
            websocket.cookies.get("cairn_session", ""), token
        ) or urlsplit(
            websocket.headers.get("origin", "")
        ).netloc != websocket.headers.get("host"):
            await websocket.close(code=1008)
            return
        if not store.one("SELECT id FROM wb_projects WHERE id=?", (pid,)):
            await websocket.close(code=1008)
            return
        store.event(pid, None, "terminal.opened", {"mode": "manual"})
        await terminal_socket(
            websocket,
            store.project_dir(pid),
            lambda: store.event(pid, None, "terminal.closed", {"mode": "manual"}),
        )

    static = Path(__file__).parent / "static"
    if static.is_dir():
        if (static / "assets").is_dir():
            app.mount(
                "/assets", StaticFiles(directory=static / "assets"), name="assets"
            )

        @app.get("/")
        def index():
            return FileResponse(static / "index.html")

    return app
