import { useEffect, useRef, useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X, Copy, Check, Terminal, FileText, Activity } from "lucide-react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import cytoscape from "cytoscape";
import { useVirtualizer } from "@tanstack/react-virtual";
import { parse, stamp, type Row } from "./api";

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  wide = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  wide?: boolean;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="modal-overlay" />
        <Dialog.Content className={"modal " + (wide ? "wide" : "")}>
          <div className="modal-heading">
            <div>
              <Dialog.Title>{title}</Dialog.Title>
              <Dialog.Description>
                {description || "Cairn Workbench"}
              </Dialog.Description>
            </div>
            <Dialog.Close className="icon-button" aria-label="关闭">
              <X size={18} />
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function CopyButton({ value }: { value: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      className="icon-button"
      aria-label="复制"
      onClick={() =>
        navigator.clipboard.writeText(value).then(() => {
          setDone(true);
          setTimeout(() => setDone(false), 1200);
        })
      }
    >
      {done ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}
export function Prose({ text }: { text: string }) {
  return (
    <div className="prose">
      <Markdown remarkPlugins={[remarkGfm]}>{text}</Markdown>
    </div>
  );
}
export function Status({ value }: { value: string }) {
  return (
    <span className={"status " + value}>
      <i />
      {(
        {
          running: "正在探索",
          queued: "排队中",
          awaiting_approval: "等待确认",
          completed: "已完成",
          cancelled: "已停止",
          failed: "执行失败",
          quota_blocked: "额度不足",
          interrupted: "已中断",
        } as Record<string, string>
      )[value] || value}
    </span>
  );
}

export function ActivityFeed({
  events,
  runs,
  onSelect,
}: {
  events: Row[];
  runs: Row[];
  onSelect: (r: Row) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [follow, setFollow] = useState(true);
  // Part updates and deltas represent the same public message. Render only its latest state.
  const latest = new Map<string, Row>();
  const visible: Row[] = [];
  for (const event of events) {
    if (event.type === "assistant.delta") continue;
    if (event.type === "assistant.part") {
      latest.set(event.data.id, event);
      continue;
    }
    if (event.type === "assistant.final") {
      for (const [id, part] of latest)
        if (part.run_id === event.run_id && part.data.type === "text")
          latest.delete(id);
    }
    if (
      [
        "run.created",
        "assistant.final",
        "hint.added",
        "run.status",
        "phase.started",
        "approval.requested",
        "approval.resolved",
        "request.response",
      ].includes(event.type)
    )
      visible.push(event);
  }
  visible.push(...latest.values());
  visible.sort((a, b) => a.seq - b.seq);
  const virtual = useVirtualizer({
    count: visible.length,
    getScrollElement: () => ref.current,
    estimateSize: () => 120,
    overscan: 6,
  });
  useEffect(() => {
    if (follow && visible.length)
      virtual.scrollToIndex(visible.length - 1, { align: "end" });
  }, [events.length, follow]);
  return (
    <div className="activity-wrap">
      <div className="feed-options">
        <span>
          <Activity size={13} /> 执行记录与公开输出
        </span>
        <button
          className={"text-button " + (follow ? "accent" : "")}
          onClick={() => setFollow(!follow)}
        >
          {follow ? "自动跟随已开启" : "恢复自动跟随"}
        </button>
      </div>
      <div
        className="feed"
        ref={ref}
        onWheel={(e) => {
          if (e.deltaY < 0) setFollow(false);
        }}
      >
        {!visible.length && (
          <div className="feed-intro">
            <h2>从一个清晰的目标开始</h2>
            <p>在下方输入本次任务，按 Ctrl + Enter 开始。</p>
          </div>
        )}
        <div style={{ height: virtual.getTotalSize(), position: "relative" }}>
          {virtual.getVirtualItems().map((item) => {
            const e = visible[item.index];
            const d = e.data;
            const run = runs.find((r) => r.id === e.run_id);
            return (
              <article
                key={e.seq}
                ref={virtual.measureElement}
                data-index={item.index}
                className={"event " + e.type.replaceAll(".", "-")}
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  width: "100%",
                  transform: `translateY(${item.start}px)`,
                }}
              >
                <div className="event-marker">
                  {e.type === "run.created" ? (
                    <span className="user-avatar">你</span>
                  ) : e.type === "assistant.part" && d.type === "tool" ? (
                    <Terminal size={15} />
                  ) : (
                    <div className="cairn-mark mini">
                      <span />
                      <span />
                      <span />
                    </div>
                  )}
                </div>
                <div className="event-body">
                  <div className="event-meta">
                    <b>
                      {e.type === "run.created"
                        ? "你"
                        : e.type === "hint.added"
                          ? "补充引导"
                          : e.type.startsWith("approval")
                            ? "操作确认"
                            : e.type === "phase.started"
                              ? "探索阶段"
                              : "Cairn"}
                    </b>
                    <time>{stamp(e.created_at)}</time>
                    {run && (
                      <button
                        className="text-button"
                        onClick={() => onSelect(run)}
                      >
                        {run.id.slice(-6)}
                      </button>
                    )}
                  </div>
                  {e.type === "run.created" ? (
                    <p className="user-message">{d.prompt}</p>
                  ) : e.type === "assistant.final" ? (
                    <>
                      <Prose text={d.text} />
                      <div className="output-footer">
                        <CopyButton value={d.text} />
                        <span>
                          {d.cost === 0
                            ? "费用 $0"
                            : `费用 $${Number(d.cost).toFixed(4)}`}
                        </span>
                      </div>
                    </>
                  ) : e.type === "hint.added" ? (
                    <p>
                      {d.content}
                      <small className="muted block">
                        在下一个探索决策阶段读取
                      </small>
                    </p>
                  ) : e.type === "run.status" ? (
                    <>
                      <Status value={d.status} />
                      {d.error && <div className="error-detail">{d.error}</div>}
                    </>
                  ) : e.type === "phase.started" ? (
                    <details className="tool-card">
                      <summary>查看本阶段任务上下文</summary>
                      <pre>{d.prompt}</pre>
                    </details>
                  ) : e.type === "assistant.part" ? (
                    d.type === "tool" ? (
                      <details className="tool-card">
                        <summary>
                          <Terminal size={14} />
                          {d.tool}
                          <span>{d.state?.status}</span>
                        </summary>
                        <pre>{JSON.stringify(d.state, null, 2)}</pre>
                      </details>
                    ) : (
                      <Prose text={d.text} />
                    )
                  ) : e.type === "approval.requested" ? (
                    <div className="inline-notice amber">
                      操作已暂停，请在「待我确认」中审核真实参数。
                    </div>
                  ) : e.type === "approval.resolved" ? (
                    <p className="muted">
                      {d.decision === "once"
                        ? "已批准本次操作"
                        : "已拒绝本次操作"}
                    </p>
                  ) : e.type === "request.response" ? (
                    <details className="tool-card">
                      <summary>HTTP {d.status} · 请求完成</summary>
                      <pre>{d.body}</pre>
                    </details>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function Graph({
  nodes,
  onSelect,
}: {
  nodes: Row[];
  onSelect: (n: Row) => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const cy = useRef<cytoscape.Core | null>(null);
  const [query, setQuery] = useState("");
  const [cutoff, setCutoff] = useState(0);
  useEffect(() => {
    setCutoff(nodes.length);
  }, [nodes.length]);
  useEffect(() => {
    if (!container.current) return;
    const visible = nodes.slice(0, cutoff);
    const ids = new Set(visible.map((n) => n.id));
    const graph = cytoscape({
      container: container.current,
      elements: [
        ...visible.map((n) => ({
          data: {
            id: n.id,
            label:
              n.description.length > 45
                ? n.description.slice(0, 45) + "…"
                : n.description,
            kind: n.kind,
          },
        })),
        ...visible.flatMap((n) =>
          parse(n.sources)
            .filter((s: string) => ids.has(s))
            .map((s: string) => ({
              data: { id: s + "-" + n.id, source: s, target: n.id },
            })),
        ),
      ],
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#282b30",
            "border-color": "#555a64",
            "border-width": 1.5,
            label: "data(label)",
            color: "#e6e7eb",
            "font-size": 11,
            "text-wrap": "wrap",
            "text-max-width": "160px",
            "text-valign": "center",
            shape: "round-rectangle",
            width: 190,
            height: 70,
            padding: "10px",
          },
        },
        {
          selector: 'node[kind="origin"]',
          style: { "border-color": "#638bf5" },
        },
        { selector: 'node[kind="goal"]', style: { "border-color": "#bc9b68" } },
        { selector: 'node[kind="fact"]', style: { "border-color": "#69a591" } },
        {
          selector: 'node[kind="intent"]',
          style: { "border-style": "dashed", "border-color": "#a6a9b0" },
        },
        {
          selector: 'node[kind="complete"]',
          style: { "background-color": "#244737", "border-color": "#64ae8d" },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#646b77",
            "target-arrow-color": "#646b77",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
          },
        },
        {
          selector: ":selected",
          style: { "border-color": "#88aaff", "border-width": 3 },
        },
        { selector: ".faded", style: { opacity: 0.18 } },
      ],
      layout: {
        name: "breadthfirst",
        directed: true,
        padding: 55,
        spacingFactor: 1.3,
      },
      minZoom: 0.15,
      maxZoom: 2,
    });
    const fit = () => {
      graph.resize();
      graph.fit(undefined, 45);
      if (graph.zoom() > 1) {
        graph.zoom(1);
        graph.center();
      }
    };
    const updateTheme = () => {
      const css = getComputedStyle(document.documentElement);
      const color = (name: string) => css.getPropertyValue(name).trim();
      graph
        .style()
        .selector("node")
        .style({
          "background-color": color("--surface"),
          "border-color": color("--muted"),
          color: color("--text"),
          "font-family": css.fontFamily,
        })
        .selector('node[kind="origin"]')
        .style({ "border-color": color("--accent") })
        .selector('node[kind="goal"]')
        .style({ "border-color": color("--amber") })
        .selector('node[kind="fact"]')
        .style({ "border-color": color("--green") })
        .selector('node[kind="intent"]')
        .style({ "border-color": color("--muted") })
        .selector('node[kind="complete"]')
        .style({
          "background-color": color("--accent-bg"),
          "border-color": color("--green"),
        })
        .selector("edge")
        .style({
          "line-color": color("--muted"),
          "target-arrow-color": color("--muted"),
        })
        .selector(":selected")
        .style({ "border-color": color("--accent") })
        .update();
    };
    updateTheme();
    const themeObserver = new MutationObserver(updateTheme);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    const resize = new ResizeObserver(fit);
    resize.observe(container.current);
    fit();
    cy.current = graph;
    graph.on("tap", "node", (e) => {
      const node = nodes.find((n) => n.id === e.target.id());
      if (node) onSelect(node);
      graph.elements().removeClass("faded");
      graph
        .elements()
        .difference(e.target.closedNeighborhood())
        .addClass("faded");
    });
    graph.on("tap", (e) => {
      if (e.target === graph) graph.elements().removeClass("faded");
    });
    return () => {
      themeObserver.disconnect();
      resize.disconnect();
      graph.destroy();
      cy.current = null;
    };
  }, [nodes, cutoff]);
  useEffect(() => {
    const graph = cy.current;
    if (!graph) return;
    graph.elements().removeClass("faded");
    if (query)
      graph
        .nodes()
        .filter(
          (n) =>
            !String(n.data("label"))
              .toLowerCase()
              .includes(query.toLowerCase()),
        )
        .addClass("faded");
  }, [query]);
  return (
    <div className="graph-view">
      <div className="view-toolbar">
        <input
          className="search-field"
          placeholder="搜索事实与意图…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <button
          className="button secondary"
          onClick={() => cy.current?.fit(undefined, 50)}
        >
          适应画布
        </button>
        <span className="muted">
          {cutoff} / {nodes.length} 节点
        </span>
      </div>
      <div ref={container} className="graph-canvas" />
      <div className="graph-footer">
        <span>历史回放</span>
        <input
          aria-label="图谱历史"
          type="range"
          min={0}
          max={nodes.length}
          value={cutoff}
          onChange={(e) => setCutoff(Number(e.target.value))}
        />
        <small>只回放记录，不撤销真实操作</small>
      </div>
    </div>
  );
}
