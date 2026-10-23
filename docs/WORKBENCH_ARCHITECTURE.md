# Workbench architecture and invariants

The Workbench is an independent control plane alongside the original Cairn server. It does not change the original server's database or run the old dispatcher against its own database. Its bounded bootstrap → reason → explore loop reuses Cairn's output contracts and Fact/Intent/Hint model.

## Owners

| State | Owner | Persistence |
|---|---|---|
| Projects, runs, approvals, graph, findings | Workbench API/runner through Store | SQLite WAL |
| Raw agent sessions and provider credentials | Managed OpenCode server | Private per-project provider directory |
| Execution permission | OpenCode policy, fulfilled only by explicit Workbench approval | Local approval row plus remote request |
| HTTP replay permission | Workbench API | One approval for one request |
| Identity secrets | Vault | Fernet ciphertext; key in private data directory |
| UI state | Browser | Layout/theme/recent project only; no credentials |
| Evidence | Artifact API | Immutable files with SHA-256 and DB association |

## Enforced invariants

1. Cancellation is terminal; late model output cannot overwrite cancelled status.
2. Restart marks unfinished runs interrupted; no external action is silently replayed.
3. Approval is atomically claimed before contacting a runtime; duplicate replies return 409. An ambiguous remote failure expires approval instead of automatically retrying it.
4. HTTP replay checks exact scheme, host, port and path boundary, including exclusions, both before and after approval. Redirects are disabled.
5. Findings can reference only evidence and runs from their project. Confirmed findings require evidence and reproduction steps.
6. The browser never receives identity ciphertext, encryption keys or provider API keys.
7. The default model and auxiliary model are free DeepSeek. Quota retry messages abort the owned session; no paid fallback is configured.
8. Graph updates and corresponding graph events commit in the same transaction.
9. Imported/model text is untrusted: Markdown cannot run HTML; exported HTML escapes all report content.
10. The API is loopback-only and authenticated; mutating cross-origin requests and cross-origin terminal sockets are rejected.

## Interfaces

`/api/v2`: login, overview, projects, runs/stop, hints, resumable SSE events, approvals, artifacts, findings, identities, requests/import/replay, reports, diagnostics, backups and manual terminal WebSocket. See authenticated `/openapi.json` for exact models. SSE `seq` is the durable cursor; clients deduplicate and reconnect using Last-Event-ID.

Run status: queued → running ↔ awaiting_approval → completed/failed/quota_blocked/interrupted/cancelled. A new attempt is a new run with parent_id; a forked agent session does not roll back external changes.

## Execution boundary

Local WSL mode uses the current user's permissions. Tool approval is not an OS sandbox or a network firewall. Arbitrary shell commands always ask; child-agent tools are disabled in the controlled runtime. Manual terminals execute only user-entered commands and are separate from agent execution. Closing a terminal sends SIGHUP to its process group.

## Compatibility and migrations

Workbench data is independent of legacy Cairn. `migrate_legacy.py` opens the source in SQLite read-only mode and copies projects/graph/hints, with idempotency markers. Migration versions are recorded in wb_migrations. Backups include database, project evidence, identity key and local access token; restoring requires a new empty directory.

## Validation levels

Protocol simulations are CI evidence only. They verify approval/reject/cancel/quota behavior without model credentials. Live `smoke_live.py` exercises the installed OpenCode server and must be reported separately. Windows installer signing, public releases, clean-machine testing and performance targets require their own evidence; successful compilation does not imply these gates passed.
