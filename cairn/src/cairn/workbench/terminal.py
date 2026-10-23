"""Explicitly opened manual project terminals. Agent tools do not use this route."""

import asyncio
import json
import os
import signal

from fastapi import WebSocket


async def terminal_socket(websocket: WebSocket, directory, on_close):
    await websocket.accept()
    if os.name == "nt":
        await websocket.send_text("\r\n项目终端需要 WSL Linux 运行环境。\r\n")
        await websocket.close()
        return
    import fcntl
    import pty
    import struct
    import termios

    pid, master = pty.fork()
    if pid == 0:
        os.chdir(directory)
        os.environ["TERM"] = "xterm-256color"
        os.execv("/bin/bash", ["bash", "--noprofile", "--norc"])

    async def read():
        try:
            while True:
                content = await asyncio.to_thread(os.read, master, 8192)
                if not content:
                    break
                await websocket.send_bytes(content)
        except (OSError, RuntimeError):
            pass

    reader = asyncio.create_task(read())
    try:
        while True:
            payload = json.loads(await websocket.receive_text())
            if payload.get("type") == "resize":
                cols, rows = (
                    max(20, min(400, int(payload["cols"]))),
                    max(5, min(150, int(payload["rows"]))),
                )
                fcntl.ioctl(
                    master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0)
                )
            elif payload.get("type") == "data":
                os.write(master, str(payload.get("data", ""))[:16384].encode())
    except Exception:
        pass
    finally:
        try:
            os.killpg(pid, signal.SIGHUP)
        except ProcessLookupError:
            pass
        os.close(master)
        reader.cancel()
        await asyncio.to_thread(os.waitpid, pid, 0)
        on_close()
