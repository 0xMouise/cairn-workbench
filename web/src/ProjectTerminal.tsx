import { useEffect, useRef, useState } from "react";
import { Terminal as TerminalIcon, Square } from "lucide-react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
export default function ProjectTerminal({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false);
  const [connection, setConnection] = useState("connecting");
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open || !ref.current) return;
    setConnection("connecting");
    let queuedInput = "";
    let inputOverflow = false;
    const terminal = new Terminal({
      fontFamily: "Cascadia Code,Consolas,monospace",
      fontSize: 12,
      cursorBlink: true,
      theme: { background: "#171819", foreground: "#e8e9eb" },
      convertEol: true,
    });
    const fit = new FitAddon();
    terminal.loadAddon(fit);
    terminal.open(ref.current);
    fit.fit();
    terminal.writeln(
      "Cairn · 手动项目终端。你输入的命令会以当前用户权限执行。",
    );
    const socket = new WebSocket(
      `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/v2/projects/${projectId}/terminal`,
    );
    socket.binaryType = "arraybuffer";
    socket.onopen = () => {
      setConnection("connected");
      socket.send(
        JSON.stringify({
          type: "resize",
          cols: terminal.cols,
          rows: terminal.rows,
        }),
      );
      if (queuedInput) {
        socket.send(JSON.stringify({ type: "data", data: queuedInput }));
        queuedInput = "";
      }
      terminal.focus();
    };
    socket.onmessage = (e) =>
      terminal.write(
        typeof e.data === "string" ? e.data : new Uint8Array(e.data),
      );
    socket.onclose = () => {
      setConnection("closed");
      queuedInput = "";
      terminal.options.disableStdin = true;
      terminal.writeln("\r\n[终端连接已关闭]");
    };
    const input = terminal.onData((data) => {
      if (socket.readyState === 1)
        socket.send(JSON.stringify({ type: "data", data }));
      else if (socket.readyState === 0 && !inputOverflow) {
        if (queuedInput.length + data.length <= 16384) queuedInput += data;
        else {
          queuedInput = "";
          inputOverflow = true;
          terminal.writeln(
            "\r\n[连接中输入过长，缓冲已清空，请连接就绪后重新输入]",
          );
        }
      }
    });
    const observer = new ResizeObserver(() => {
      fit.fit();
      if (socket.readyState === 1)
        socket.send(
          JSON.stringify({
            type: "resize",
            cols: terminal.cols,
            rows: terminal.rows,
          }),
        );
    });
    observer.observe(ref.current);
    return () => {
      observer.disconnect();
      input.dispose();
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.close();
      terminal.dispose();
    };
  }, [open, projectId]);
  return (
    <div className="terminal-view">
      <div className="view-toolbar">
        <span className="muted">手动终端 · 项目工作目录 · 当前用户权限</span>
        {open && (
          <span className="terminal-connection" role="status">
            {connection === "connected"
              ? "终端已连接"
              : connection === "closed"
                ? "连接已关闭"
                : "正在连接终端…"}
          </span>
        )}
        {open && (
          <button className="button secondary" onClick={() => setOpen(false)}>
            <Square size={12} />
            关闭终端
          </button>
        )}
      </div>
      {open ? (
        <div className="terminal-container" ref={ref} />
      ) : (
        <div className="empty">
          <div>
            <TerminalIcon />
          </div>
          <h3>打开项目终端</h3>
          <p>
            命令由你直接输入并执行。关闭终端会结束此会话，
            <br />
            已产生的文件与外部修改会保留。
          </p>
          <button className="button secondary" onClick={() => setOpen(true)}>
            打开手动终端
          </button>
        </div>
      )}
    </div>
  );
}
