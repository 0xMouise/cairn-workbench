# Contributing to Cairn Workbench

Keep changes scoped to one user-visible behavior or invariant. Preserve the original Cairn server's compatibility and never run a new dispatcher against a user's legacy database.

## Local checks

- Backend: Python 3.12+, install `cairn/requirements-workbench.lock`, the editable cairn package, pytest and httpx. Run `pytest cairn/tests -q` on Linux/WSL.
- Frontend: `cd web && npm ci && npm run build`. Formatting: `npx prettier --check src tests vite.config.ts playwright.config.ts`.
- Browser: start `scripts/serve_workbench.py` with a private temporary data directory, then `npm run test:e2e` in web. Set `CAIRN_E2E_TOKEN_FILE` when using another test data directory.
- Desktop: Rust stable and Visual Studio C++ tools, `npm run tauri build` in web. Windows release CI produces unsigned preview packages only.

Use protocol simulations for CI. Never add real credentials, targets or identity data to fixtures. Real model smoke tests are opt-in and must be described separately from simulated results. Only use locally owned or explicitly authorized environments for external actions.

## Review expectations

For execution changes, include approval/reject/cancel/restart tests. For evidence changes, include cross-project isolation and export checks. For visual changes, inspect light/dark themes and 1280×800 layout. Report exact verification limits; do not describe a compiled package as clean-machine tested or signed.

Retain AGPL-3.0 and third-party notices. Contributions are distributed under the repository's existing license.
