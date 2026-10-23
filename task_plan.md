# Cairn Workbench implementation

## Objective
Implement the accepted Windows + WSL, Chinese-first open-source security workbench plan. Preserve the existing deployment and data. No paid fallback. Key operations require approval.

## Phases
1. P0: Independent fork, persistence, authenticated local API, OpenCode event/approval/cancel adapter — implemented and protocol-tested; live-model completion limited by provider quota/response.
2. P1: React workbench, themes, streaming activity, approvals, diagnostics and Tauri desktop — implemented; installed native UI verified.
3. P2: Graph, API imports/replay, encrypted identities, evidence/findings/PDF reports, recovery — implemented; local transport and browser tests passed.
4. P3: Windows unsigned preview, installation, migrations/backups, CI/docs, end-to-end QA — implemented locally; published successfully. Remote Linux and Windows CI passed. Signing/clean-machine/soak/performance gates remain release debt.

## Completion gates
Production API integration exercised independently from simulated CI fixtures. Existing tests pass. Approval reject cannot execute. No secret in reports/logs. UI visually reviewed. Build artifacts identified honestly. External model quota and signing availability are separate release dependencies.

## 0.1.1 visual refinement
Typography, neutral palettes, project overview, compact empty states, graph/terminal theme integration implemented. Browser checks and native visual review passed; 0.1.1 NSIS built and installed; GitHub update being published.
