# 0.1.0 Preview validation

Verified on the user's Windows x64 + WSL Kali environment, 2026-10-23.

| Check | Evidence / result |
|---|---|
| Linux backend regression | 119 tests passed using the locked runtime environment |
| Protocol simulation | Approve/reject/cancel/quota control; bounded bootstrap → reason → explore; invalid fact references rejected |
| Real HTTP transport | Local owned HTTP server received one request only after approval, with decrypted test identity; duplicate approval did not replay |
| Browser workflows | 3 Playwright tests passed against the installed WSL service: project/evidence/finding/request/report/themes, keyboard/settings, real manual PTY |
| Event volume | Latest 10,000 events retrieved in order with durable cursors; UI uses a virtualized activity list |
| PDF | Direct PDF download passed browser/API checks; Chinese sample rendered and visually inspected; text extraction retained Chinese |
| Desktop build | Tauri Windows x64 executable and NSIS setup compiled successfully |
| Desktop install | Silent NSIS install returned exit code 0; executable and runtime resource present |
| Native rendering | Installed WebView connected and authenticated to the WSL service; welcome UI screenshot in images/workbench-desktop.png |
| Local delivery | Desktop shortcut created; original Cairn 18000 deployment preserved; Workbench uses 18100 with an independent DB |
| Data recovery | Complete backup/restore, unsafe archive rejection, read-only idempotent legacy import tested |
| Credential controls | Identity/provider ciphertext not returned to the browser; validation errors omit submitted input; reports redact common secrets |
| Formatting | Frontend Prettier, Rust fmt, Python Ruff format; unused Python imports removed |

## Separate live-model evidence

The actual installed OpenCode server was inspected and contacted. Free DeepSeek requests encountered provider free-tier limits; some WSL calls timed out. A complete real-model research task has **not** passed acceptance. Protocol fixtures are explicitly simulations and must not be described as successful live model execution. No paid fallback or client-identity spoofing was added.

## Release limitations

The package is an unsigned preview. Clean Windows machine provisioning, code signing, cold-start performance, thousand-node graph benchmarks, and long-duration soak testing remain separate gates. Local installation/renderer verification does not establish those gates. The app does not advertise OS sandboxing, environment rollback, or remote action reversal.

GitHub Actions is configured for Linux tests/browser checks and Windows preview builds. Remote CI status is visible in GitHub; local results above do not imply remote CI succeeded.

The first remote Linux browser run exposed a terminal handshake/input race. The terminal now displays readiness, buffers input until the WebSocket opens, discards overflow without executing a partial buffered command, and removes socket callbacks on disposal. The browser check waits for the actual connected state before issuing its test command.

## Remote release verification

Commit `9c0a3f6` passed both Linux and Windows jobs: https://github.com/0xMouise/cairn-workbench/actions/runs/39895835323

The public preview installer SHA-256 digest matches the locally installed and inspected package. Release: https://github.com/0xMouise/cairn-workbench/releases/tag/v0.1.0-workbench-preview
