from __future__ import annotations

import json
import re
import sqlite3
import uuid
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid(prefix: str) -> str:
    return prefix + "_" + uuid.uuid4().hex[:16]


def redact(value):
    if not isinstance(value, str):
        sensitive = {
            "authorization",
            "proxyauthorization",
            "password",
            "passwd",
            "secret",
            "clientsecret",
            "cookie",
            "setcookie",
            "token",
            "apikey",
            "xapikey",
            "accesstoken",
            "refreshtoken",
            "xauthtoken",
            "xcsrftoken",
            "xxsrftoken",
            "csrftoken",
            "xauthorization",
        }

        def clean(item):
            if isinstance(item, dict):
                return {
                    key: "[REDACTED]"
                    if str(key).lower().replace("-", "").replace("_", "") in sensitive
                    else clean(val)
                    for key, val in item.items()
                }
            if isinstance(item, list):
                return [clean(val) for val in item]
            return redact(item) if isinstance(item, str) else item

        return json.dumps(clean(value), ensure_ascii=False)
    text = value
    text = re.sub(r"(?i)(bearer\s+)[\w.\-]+", r"\1[REDACTED]", text)
    text = re.sub(r"\bsk[-.][A-Za-z0-9_.-]{8,}", "[REDACTED]", text)
    text = re.sub(
        r'(?i)((?:api[_-]?key|authorization|password|cookie|set-cookie|token)["\s]*[:=]["\s]*)[^\s,"\\}]+',
        r"\1[REDACTED]",
        text,
    )
    return text


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS wb_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wb_projects(id TEXT PRIMARY KEY, title TEXT NOT NULL, origin TEXT NOT NULL, goal TEXT NOT NULL,
 scope TEXT NOT NULL DEFAULT '[]', excluded TEXT NOT NULL DEFAULT '[]', archived INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wb_runs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES wb_projects(id),
 prompt TEXT NOT NULL, status TEXT NOT NULL, session_id TEXT, parent_id TEXT, step INTEGER NOT NULL DEFAULT 0,
 model TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT, cost REAL NOT NULL DEFAULT 0,
 tokens INTEGER NOT NULL DEFAULT 0, max_steps INTEGER NOT NULL DEFAULT 6, timeout INTEGER NOT NULL DEFAULT 600);
CREATE TABLE IF NOT EXISTS wb_events(seq INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, run_id TEXT,
 type TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS wb_events_run_seq ON wb_events(run_id,seq);
CREATE TABLE IF NOT EXISTS wb_approvals(id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES wb_runs(id),
 remote_id TEXT NOT NULL, permission TEXT NOT NULL, details TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 created_at TEXT NOT NULL, resolved_at TEXT, UNIQUE(run_id, remote_id));
CREATE TABLE IF NOT EXISTS wb_findings(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES wb_projects(id),
 run_id TEXT, title TEXT NOT NULL, severity TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'draft',
 description TEXT NOT NULL, reproduction TEXT NOT NULL DEFAULT '', impact TEXT NOT NULL DEFAULT '',
 evidence TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wb_artifacts(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES wb_projects(id),
 run_id TEXT, name TEXT NOT NULL, path TEXT NOT NULL, media_type TEXT NOT NULL, size INTEGER NOT NULL, sha256 TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wb_requests(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES wb_projects(id),
 method TEXT NOT NULL, url TEXT NOT NULL, headers TEXT NOT NULL DEFAULT '{}', body TEXT NOT NULL DEFAULT '',
 response TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wb_graph(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES wb_projects(id),
 run_id TEXT, kind TEXT NOT NULL, description TEXT NOT NULL, sources TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wb_hints(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES wb_projects(id),
 run_id TEXT, content TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS wb_identities(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES wb_projects(id),
 name TEXT NOT NULL, encrypted TEXT NOT NULL, header_names TEXT NOT NULL, created_at TEXT NOT NULL);
"""


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "workbench.db"
        with self.connect() as c:
            c.executescript(SCHEMA)
            c.execute("INSERT OR IGNORE INTO wb_migrations VALUES(1,?)", (now(),))
            columns = {r[1] for r in c.execute("PRAGMA table_info(wb_requests)")}
            if "identity_id" not in columns:
                c.execute("ALTER TABLE wb_requests ADD COLUMN identity_id TEXT")
            c.execute("INSERT OR IGNORE INTO wb_migrations VALUES(2,?)", (now(),))

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA busy_timeout=15000")
        try:
            with c:
                yield c
        finally:
            c.close()

    def all(self, sql, args=()):
        with self.connect() as c:
            return [dict(r) for r in c.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        rows = self.all(sql, args)
        return rows[0] if rows else None

    def execute(self, sql, args=()):
        with self.connect() as c:
            c.execute(sql, args)

    def event(self, project_id, run_id, kind, data, c=None):
        args = (project_id, run_id, kind, redact(data), now())
        if c is not None:
            return c.execute(
                "INSERT INTO wb_events(project_id,run_id,type,data,created_at) VALUES(?,?,?,?,?)",
                args,
            ).lastrowid
        with self.connect() as conn:
            return self.event(project_id, run_id, kind, data, conn)

    def state(self, run_id, status, error=None):
        with self.connect() as c:
            row = c.execute("SELECT * FROM wb_runs WHERE id=?", (run_id,)).fetchone()
            if not row:
                return
            # Terminal cancellation must never be overwritten by a late model response.
            if row["status"] == "cancelled" and status != "cancelled":
                return
            c.execute(
                "UPDATE wb_runs SET status=?,error=?,updated_at=? WHERE id=?",
                (status, redact(error) if error else None, now(), run_id),
            )
            self.event(
                row["project_id"],
                run_id,
                "run.status",
                {"status": status, "error": error},
                c,
            )

    def graph(self, project_id, run_id, kind, description, sources=None):
        ident = uid("node")
        with self.connect() as c:
            c.execute(
                "INSERT INTO wb_graph VALUES(?,?,?,?,?,?,?)",
                (
                    ident,
                    project_id,
                    run_id,
                    kind,
                    description,
                    json.dumps(sources or []),
                    now(),
                ),
            )
            self.event(
                project_id,
                run_id,
                "graph.added",
                {
                    "id": ident,
                    "kind": kind,
                    "description": description,
                    "sources": sources or [],
                },
                c,
            )
        return ident

    def recover(self):
        for run in self.all(
            "SELECT * FROM wb_runs WHERE status IN ('running','awaiting_approval','stopping','queued')"
        ):
            self.state(
                run["id"],
                "interrupted",
                "服务已重启。请复核已执行操作，再创建新的尝试。",
            )
        self.execute(
            "UPDATE wb_approvals SET status='expired',resolved_at=? WHERE status='pending'",
            (now(),),
        )

    def backup(self, target: Path):
        with self.connect() as source, closing(sqlite3.connect(target)) as dest:
            source.backup(dest)

    def project_dir(self, project_id):
        if not re.fullmatch(r"project_[a-f0-9]{16}", project_id):
            raise ValueError("Invalid project identifier")
        path = self.root / "projects" / project_id
        path.mkdir(parents=True, exist_ok=True)
        return path
