# Findings
- Baseline upstream 8e7e0ea, Cairn 0.2.1; FastAPI/Python >=3.12, SQLite, Alpine single-file UI, graph via Cytoscape.
- Existing deployment remains /home/kali/apps/cairn on port 18000. New workbench will use 18100 and an independent database.
- Existing OpenCode CLI adapter uses --auto; new runner must use OpenCode server with explicit ask permissions.
- Previous free model call from Windows succeeded at zero cost; WSL returned quota exhaustion. This must be surfaced without paid fallback.
- Windows Rust toolchain exists under ~/.cargo/bin, not on shell PATH.
