from __future__ import annotations

import json
from typing import Any

from cairn.dispatcher.config import WorkerConfig
from cairn.dispatcher.workers.base import DriverResult, WorkerDriver
from cairn.dispatcher.workers.health import HealthResult


class OpenCodeDriver(WorkerDriver):
    """Local OpenCode CLI backend; provider access remains inside OpenCode."""

    type_name = "opencode"

    def local_binary(self) -> str:
        return "opencode"

    def check_health(self, worker: WorkerConfig, *, timeout: float) -> HealthResult:
        return HealthResult(False, None, "OpenCode supports local execution only")

    def _argv(self, worker: WorkerConfig, prompt: str, session: str | None) -> list[str]:
        argv = ["opencode", "run", "--pure", "--auto", "--format", "json",
                "--model", worker.env.get("OPENCODE_MODEL", "opencode/deepseek-v4.1-flash-free")]
        if session:
            argv.extend(["--session", session])
        argv.extend(["--", prompt])
        return argv

    def build_execute(self, worker: WorkerConfig, prompt: str, session: str | None) -> DriverResult:
        return DriverResult(argv=self._argv(worker, prompt, session), session=session)

    def build_conclude(self, worker: WorkerConfig, prompt: str, session: str) -> list[str]:
        return self._argv(worker, prompt, session)

    @staticmethod
    def _events(stdout: str) -> list[dict[str, Any]]:
        events = []
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return events

    def extract_session(self, session: str | None, stdout: str, stderr: str) -> str | None:
        return session or next((e["sessionID"] for e in self._events(stdout)
                                if isinstance(e.get("sessionID"), str)), None)

    def extract_response_text(self, stdout: str, stderr: str) -> str:
        events = self._events(stdout)
        errors = [e for e in events if e.get("type") == "error"]
        if errors:
            raise RuntimeError("OpenCode worker failed: " + json.dumps(errors[-1].get("error")))
        return "\n".join(e.get("part", {}).get("text", "") for e in events
                         if e.get("type") == "text")
