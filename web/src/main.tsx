import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Plus,
  Search,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  PanelRightClose,
  PanelRightOpen,
  Sun,
  Moon,
  Monitor,
  ArrowUp,
  Square,
  Paperclip,
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  Activity,
  GitBranch,
  ShieldCheck,
  FileText,
  Globe,
  Layers,
  ArrowUpRight,
  Download,
  Archive,
  RefreshCw,
  CircleHelp,
  Check,
  X,
  MoreHorizontal,
  Command,
  AlertTriangle,
  Inbox,
  LoaderCircle,
  Terminal,
  FileSearch,
  Wifi,
  WifiOff,
  Copy,
  ExternalLink,
} from "lucide-react";
import { api, parse, stamp, statuses, type Row } from "./api";
import {
  Modal,
  Status,
  Prose,
  Graph,
  ActivityFeed,
  CopyButton,
} from "./components";
import "./styles.css";
const ProjectTerminal = React.lazy(() => import("./ProjectTerminal"));

const LIVE = ["queued", "running", "awaiting_approval", "stopping"];
const tabs = [
  ["activity", "活动", Activity],
  ["graph", "探索图", GitBranch],
  ["findings", "发现", ShieldCheck],
  ["requests", "请求", Globe],
  ["artifacts", "产物", Layers],
  ["terminal", "终端", Terminal],
] as const;
const initialProject = {
  title: "",
  origin: "",
  goal: "",
  scope: "",
  excluded: "",
};
const initialFinding = {
  title: "",
  severity: "medium",
  status: "draft",
  description: "",
  reproduction: "",
  impact: "",
  evidence: [] as string[],
  run_id: null as string | null,
};
const severity: Record<string, string> = {
  info: "信息",
  low: "低危",
  medium: "中危",
  high: "高危",
  critical: "严重",
};

function App() {
  const [ready, setReady] = useState(false),
    [loginRequired, setLoginRequired] = useState(false),
    [token, setToken] = useState("");
  const [overview, setOverview] = useState<Row>({
      projects: [],
      runs: [],
      approvals: [],
      model: "",
    }),
    [detail, setDetail] = useState<Row | null>(null);
  const [selected, setSelected] = useState(
      localStorage.getItem("cairn.project") || "",
    ),
    [selectedRun, setSelectedRun] = useState("");
  const [tab, setTab] = useState("activity"),
    [filter, setFilter] = useState("all"),
    [query, setQuery] = useState(""),
    [command, setCommand] = useState("");
  const [dialog, setDialog] = useState(""),
    [projectForm, setProjectForm] = useState(initialProject),
    [findingForm, setFindingForm] = useState(initialFinding),
    [editingFinding, setEditingFinding] = useState("");
  const [requestForm, setRequestForm] = useState({
    method: "GET",
    url: "",
    headers: "{}",
    body: "",
    identity_id: "",
  });
  const [identityForm, setIdentityForm] = useState({
    name: "",
    headers: '{\n  \"Authorization\": \"Bearer …\"\n}',
  });
  const [events, setEvents] = useState<Row[]>([]),
    [inspected, setInspected] = useState<Row | null>(null),
    [diagnostics, setDiagnostics] = useState<Row | null>(null);
  const [composer, setComposer] = useState(""),
    [busy, setBusy] = useState(false),
    [toast, setToast] = useState<{ text: string; error?: boolean } | null>(
      null,
    );
  const [theme, setTheme] = useState(
      localStorage.getItem("cairn.theme") || "system",
    ),
    [leftOpen, setLeftOpen] = useState(true),
    [rightOpen, setRightOpen] = useState(
      localStorage.getItem("cairn.inspector") !== "false",
    );
  const [connected, setConnected] = useState(false),
    [elapsed, setElapsed] = useState(Date.now());
  const [leftWidth, setLeftWidth] = useState(
      Number(localStorage.getItem("cairn.sidebar.width")) || 248,
    ),
    [rightWidth, setRightWidth] = useState(
      Number(localStorage.getItem("cairn.inspector.width")) || 340,
    );
  const [logQuery, setLogQuery] = useState("");
  const [proxyURL, setProxyURL] = useState("");
  const [providerKey, setProviderKey] = useState("");
  const [providerInfo, setProviderInfo] = useState<Row | null>(null);
  useEffect(() => {
    setProviderKey("");
    if (dialog === "settings")
      api("/settings/provider")
        .then(setProviderInfo)
        .catch(() => {});
  }, [dialog]);
  useEffect(() => {
    if (dialog === "settings")
      api("/settings/network")
        .then((n) => setProxyURL(n.proxy))
        .catch(() => {});
  }, [dialog]);
  const uploadRef = useRef<HTMLInputElement>(null),
    importRef = useRef<HTMLInputElement>(null),
    filePurpose = useRef("artifact");
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const currentRun: Row | undefined =
    detail?.runs.find((r: Row) => r.id === selectedRun) || detail?.runs.at(-1);
  const activeRun: Row | undefined = detail?.runs.find((r: Row) =>
    LIVE.includes(r.status),
  );
  const project = detail?.project;
  const notify = (text: string, error = false) => {
    setToast({ text, error });
    setTimeout(() => setToast(null), 5500);
  };
  const refresh = useCallback(async () => {
    try {
      const result = await api("/overview");
      setOverview(result);
      setLoginRequired(false);
      setReady(true);
      return result;
    } catch (e: any) {
      if (e.status === 401) setLoginRequired(true);
      else notify(e.message, true);
      setReady(true);
    }
  }, []);
  const load = useCallback(async (pid: string) => {
    if (!pid) {
      setDetail(null);
      setEvents([]);
      return;
    }
    try {
      const [d, ev] = await Promise.all([
        api("/projects/" + pid),
        api("/events?tail=true&project_id=" + pid),
      ]);
      if (selectedRef.current !== pid) return;
      setDetail(d);
      setEvents(ev);
      setSelectedRun(d.runs.at(-1)?.id || "");
    } catch (e: any) {
      notify(e.message, true);
    }
  }, []);
  useEffect(() => {
    (async () => {
      const params = new URLSearchParams(location.hash.slice(1));
      const launchToken = params.get("token");
      if (launchToken) {
        history.replaceState(null, "", location.pathname);
        try {
          await api("/login", "POST", { token: launchToken });
        } catch (e: any) {
          notify(e.message, true);
        }
      }
      await refresh();
    })();
  }, []);
  useEffect(() => {
    if (!loginRequired && ready) load(selected);
    localStorage.setItem("cairn.project", selected);
    setInspected(null);
  }, [selected, loginRequired, ready]);
  useEffect(() => {
    if (loginRequired || !ready) return;
    let timer: ReturnType<typeof setTimeout>;
    const source = new EventSource(
      "/api/v2/events?stream=true&after=" + (overview.cursor || 0),
    );
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);
    source.onmessage = (e) => {
      const event = JSON.parse(e.data);
      if (event.project_id === selectedRef.current)
        setEvents((prev) =>
          prev.some((x) => x.seq === event.seq)
            ? prev
            : [...prev, event].slice(-10000),
        );
      if (event.type !== "assistant.delta" && event.type !== "assistant.part") {
        clearTimeout(timer);
        timer = setTimeout(() => {
          refresh();
          if (selectedRef.current)
            api("/projects/" + selectedRef.current)
              .then((d) => setDetail(d))
              .catch(() => {});
        }, 250);
      }
      if (
        ["approval.requested", "run.status"].includes(event.type) &&
        "Notification" in window &&
        Notification.permission === "granted" &&
        document.hidden
      )
        new Notification(
          event.type === "approval.requested"
            ? "Cairn · 等待你的确认"
            : "Cairn · 任务状态更新",
          {
            body: event.data.status
              ? statuses[event.data.status]
              : "操作已暂停，请查看审批详情。",
          },
        );
    };
    return () => {
      source.close();
      clearTimeout(timer);
    };
  }, [ready, loginRequired]);
  useEffect(() => {
    const media = matchMedia("(prefers-color-scheme: dark)");
    const update = () =>
      (document.documentElement.dataset.theme =
        theme === "system" ? (media.matches ? "dark" : "light") : theme);
    update();
    localStorage.setItem("cairn.theme", theme);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [theme]);
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        setDialog((v) => (v === "search" ? "" : "search"));
      }
    };
    window.addEventListener("keydown", handler);
    const timer = setInterval(() => setElapsed(Date.now()), 1000);
    return () => {
      window.removeEventListener("keydown", handler);
      clearInterval(timer);
    };
  }, []);
  const act = async (fn: () => Promise<any>, message?: string) => {
    setBusy(true);
    try {
      await fn();
      await refresh();
      if (selectedRef.current) await load(selectedRef.current);
      if (message) notify(message);
      return true;
    } catch (e: any) {
      notify(e.message, true);
      return false;
    } finally {
      setBusy(false);
    }
  };
  const choose = (pid: string) => {
    setSelected(pid);
    setDialog("");
    setTab("activity");
  };
  const resize = (side: "left" | "right", e: React.PointerEvent) => {
    e.preventDefault();
    const start = e.clientX,
      old = side === "left" ? leftWidth : rightWidth;
    const move = (ev: PointerEvent) => {
      const next = Math.max(
        side === "left" ? 200 : 280,
        Math.min(
          side === "left" ? 330 : 520,
          old + (ev.clientX - start) * (side === "left" ? 1 : -1),
        ),
      );
      side === "left" ? setLeftWidth(next) : setRightWidth(next);
      localStorage.setItem(
        side === "left" ? "cairn.sidebar.width" : "cairn.inspector.width",
        String(next),
      );
    };
    const end = () => {
      document.removeEventListener("pointermove", move);
      document.removeEventListener("pointerup", end);
    };
    document.addEventListener("pointermove", move);
    document.addEventListener("pointerup", end);
  };
  const createProject = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const result = await api("/projects", "POST", {
        ...projectForm,
        scope: projectForm.scope
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        excluded: projectForm.excluded
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      await refresh();
      choose(result.id);
      setProjectForm(initialProject);
      notify("项目已创建");
    } catch (e: any) {
      notify(e.message, true);
    } finally {
      setBusy(false);
    }
  };
  const send = async () => {
    if (!composer.trim() || !selected) return;
    const text = composer;
    const ok = await act(() =>
      activeRun
        ? api(`/projects/${selected}/hints`, "POST", {
            content: text,
            run_id: activeRun.id,
          })
        : api(`/projects/${selected}/runs`, "POST", {
            prompt: text,
            parent_id: currentRun?.id || null,
          }),
    );
    if (ok) setComposer("");
  };
  const upload = async (file: File) => {
    if (!selected) return;
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (const byte of bytes) binary += String.fromCharCode(byte);
    await act(
      () =>
        api(`/projects/${selected}/artifacts`, "POST", {
          name: file.name,
          content: btoa(binary),
          media_type: file.type,
          run_id: currentRun?.id || null,
        }),
      "附件已保存为项目证据",
    );
  };
  const importFile = async (file: File) => {
    try {
      const content = JSON.parse(await file.text());
      await act(
        () =>
          api(`/projects/${selected}/import`, "POST", {
            format: content.log ? "har" : "openapi",
            content,
          }),
        "接口已导入，重放前仍需确认",
      );
    } catch (e: any) {
      notify("导入失败：" + e.message, true);
    }
  };
  const openFinding = (item?: Row) => {
    setFindingForm(
      item
        ? { ...initialFinding, ...item, evidence: parse(item.evidence) }
        : initialFinding,
    );
    setEditingFinding(item?.id || "");
    setDialog("finding");
  };
  const saveFinding = async (e: React.FormEvent) => {
    e.preventDefault();
    if (
      await act(
        () =>
          api(
            editingFinding
              ? "/findings/" + editingFinding
              : `/projects/${selected}/findings`,
            editingFinding ? "PUT" : "POST",
            findingForm,
          ),
        "发现已保存",
      )
    )
      setDialog("");
  };
  const projectList = overview.projects.filter(
    (p: Row) =>
      (filter === "archived" ? p.archived : !p.archived) &&
      (filter !== "running" ||
        overview.runs.some(
          (r: Row) => r.project_id === p.id && LIVE.includes(r.status),
        )) &&
      (!query || p.title.toLowerCase().includes(query.toLowerCase())),
  );
  const inspectedRun = inspected?.kind === "run" ? inspected : currentRun;
  const displayEvents = events.filter(
    (e) =>
      (!selectedRun || e.run_id === selectedRun || !e.run_id) &&
      (!logQuery ||
        JSON.stringify(e.data).toLowerCase().includes(logQuery.toLowerCase())),
  );

  if (!ready)
    return (
      <div className="boot">
        <LoaderCircle className="spin" />
        <span>正在连接工作台…</span>
      </div>
    );
  if (loginRequired)
    return (
      <div className="login-page">
        <div className="login-card">
          <div className="cairn-mark large">
            <span />
            <span />
            <span />
          </div>
          <h1>Cairn Workbench</h1>
          <p>你的本地安全研究工作台</p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                await api("/login", "POST", { token });
                await refresh();
              } catch (e: any) {
                notify(e.message, true);
              }
            }}
          >
            <label>
              本机访问令牌
              <input
                type="password"
                autoComplete="off"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="通过桌面入口打开可自动登录"
                required
              />
            </label>
            <button className="button primary">
              进入工作台 <ArrowUpRight size={16} />
            </button>
          </form>
          <small>
            令牌保存在本地数据目录的 access-token 文件中。
            <br />
            项目、凭据与研究记录均保存在你的设备上。
          </small>
        </div>
        {toast && (
          <div role="alert" className="toast error">
            {toast.text}
          </div>
        )}
      </div>
    );

  return (
    <div
      className={
        "app " +
        (!leftOpen ? "left-hidden " : "") +
        (!rightOpen || !project ? "right-hidden" : "")
      }
      style={
        {
          "--sidebar-width": `${leftWidth}px`,
          "--inspector-width": `${rightWidth}px`,
        } as React.CSSProperties
      }
    >
      <aside className="sidebar">
        <div className="brand">
          <div className="cairn-mark">
            <span />
            <span />
            <span />
          </div>
          <div>
            <strong>Cairn</strong>
            <span>研究工作台</span>
          </div>
          <button
            className="icon-button"
            title="收起侧栏"
            onClick={() => setLeftOpen(false)}
          >
            <PanelLeftClose size={17} />
          </button>
        </div>
        <button
          aria-label="新建研究项目"
          className="new-project"
          onClick={() => setDialog("project")}
        >
          <Plus size={17} />
          新建研究项目<span>＋</span>
        </button>
        <button className="global-search" onClick={() => setDialog("search")}>
          <Search size={15} />
          <span>搜索与命令</span>
          <kbd>Ctrl K</kbd>
        </button>
        <nav className="primary-nav">
          <button
            className={filter === "all" ? "selected" : ""}
            onClick={() => {
              setFilter("all");
              choose("");
            }}
          >
            <Folder size={16} />
            所有项目
            <span>
              {overview.projects.filter((p: Row) => !p.archived).length}
            </span>
          </button>
          <button
            className={filter === "running" ? "selected" : ""}
            onClick={() => {
              setFilter("running");
              choose("");
            }}
          >
            <Activity size={16} />
            运行中
            <span>
              {overview.runs.filter((r: Row) => LIVE.includes(r.status)).length}
            </span>
          </button>
          <button onClick={() => setDialog("approvals")}>
            <ShieldCheck size={16} />
            待我确认
            {overview.approvals.length > 0 && (
              <span className="badge amber">{overview.approvals.length}</span>
            )}
          </button>
          <button
            className={filter === "archived" ? "selected" : ""}
            onClick={() => {
              setFilter("archived");
              choose("");
            }}
          >
            <Archive size={16} />
            已归档
          </button>
        </nav>
        <div className="sidebar-section-label">
          <span>{filter === "archived" ? "已归档项目" : "你的工作区"}</span>
          <button
            className="icon-button"
            aria-label="新建项目"
            onClick={() => setDialog("project")}
          >
            <Plus size={13} />
          </button>
        </div>
        <div className="project-list">
          {projectList.map((p: Row) => {
            const latest = overview.runs.find(
              (r: Row) => r.project_id === p.id,
            );
            return (
              <button
                key={p.id}
                className={
                  "project-item " + (selected === p.id ? "selected" : "")
                }
                onClick={() => choose(p.id)}
              >
                <FolderOpen size={16} />
                <span>
                  <b>{p.title}</b>
                  <small>
                    {latest ? statuses[latest.status] : "尚未开始探索"}
                  </small>
                </span>
                {latest && LIVE.includes(latest.status) && (
                  <i className="live-dot" />
                )}
              </button>
            );
          })}
          {!projectList.length && (
            <div className="sidebar-empty">
              {filter === "running"
                ? "没有运行中的项目"
                : filter === "archived"
                  ? "尚无归档项目"
                  : "创建项目，开始积累研究记录。"}
            </div>
          )}
        </div>
        <div className="sidebar-bottom">
          <div className="environment-card">
            <span className={"connection-dot " + (connected ? "online" : "")} />
            <div>
              <b>本地工作台</b>
              <small>{connected ? "事件流已连接" : "事件流重连中"}</small>
            </div>
            <span className="local-pill">本机</span>
          </div>
          <div className="sidebar-actions">
            <button
              onClick={async () => {
                setDialog("settings");
                setDiagnostics(await api("/diagnostics"));
              }}
            >
              <Settings size={16} />
              设置与诊断
            </button>
            <button
              className="icon-button"
              title="使用帮助"
              onClick={() => setDialog("help")}
            >
              <CircleHelp size={16} />
            </button>
          </div>
        </div>
        <div
          className="resize-handle left"
          onPointerDown={(e) => resize("left", e)}
        />
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="breadcrumbs">
            {!leftOpen && (
              <button
                className="icon-button"
                aria-label="展开侧栏"
                onClick={() => setLeftOpen(true)}
              >
                <PanelLeftOpen size={17} />
              </button>
            )}
            <span>工作区</span>
            <ChevronRight size={13} />
            <strong>{project?.title || "概览"}</strong>
            {project && <span className="project-label">研究项目</span>}
          </div>
          <div className="top-actions">
            <span className="engine-badge">
              <span className="live-dot" />
              DeepSeek · 免费
            </span>
            <button
              className="icon-button"
              title="切换主题"
              onClick={() =>
                setTheme(
                  document.documentElement.dataset.theme === "dark"
                    ? "light"
                    : "dark",
                )
              }
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button
              className="icon-button"
              title="切换详情栏"
              disabled={!project}
              onClick={() => {
                setRightOpen(!rightOpen);
                localStorage.setItem("cairn.inspector", String(!rightOpen));
              }}
            >
              {rightOpen ? (
                <PanelRightClose size={17} />
              ) : (
                <PanelRightOpen size={17} />
              )}
            </button>
          </div>
        </header>
        {!project ? (
          <div className="welcome">
            <div className="home-heading">
              <div>
                <h1>
                  {filter === "archived"
                    ? "已归档项目"
                    : filter === "running"
                      ? "运行中的项目"
                      : "项目"}
                </h1>
                <p>管理目标、查看进展，继续上次的工作。</p>
              </div>
              <button
                className="button primary"
                onClick={() => setDialog("project")}
              >
                <Plus size={15} />
                新建项目
              </button>
            </div>
            <div className="home-projects">
              <div className="home-list-heading">
                <span>项目名称</span>
                <span>{projectList.length} 个项目</span>
              </div>
              {projectList.length ? (
                projectList.map((p: Row) => {
                  const latest = overview.runs.find(
                    (r: Row) => r.project_id === p.id,
                  );
                  return (
                    <button
                      className="home-project-row"
                      key={p.id}
                      onClick={() => choose(p.id)}
                    >
                      <Folder size={18} />
                      <span className="home-project-info">
                        <strong>{p.title}</strong>
                        <small>{p.goal || "尚未填写研究目标"}</small>
                      </span>
                      <span className="home-project-status">
                        {latest ? statuses[latest.status] : "未开始"}
                      </span>
                      <ChevronRight size={15} />
                    </button>
                  );
                })
              ) : (
                <div className="home-empty">
                  <FolderOpen size={28} strokeWidth={1.3} />
                  <h2>
                    {filter === "all"
                      ? "还没有项目"
                      : filter === "archived"
                        ? "没有已归档的项目"
                        : "当前没有运行中的项目"}
                  </h2>
                  <p>
                    {filter === "all"
                      ? "为一个研究目标创建项目，请求、证据和结论会保存在一起。"
                      : "可以从侧栏选择其他项目，或创建一个新项目。"}
                  </p>
                  {filter === "all" && (
                    <button
                      className="button secondary"
                      onClick={() => setDialog("project")}
                    >
                      <Plus size={14} />
                      创建项目
                    </button>
                  )}
                </div>
              )}
            </div>
            <div className="home-tools">
              <button onClick={() => setDialog("search")}>
                <Search size={16} />
                <span>搜索项目与命令</span>
                <kbd>Ctrl K</kbd>
              </button>
              <button
                onClick={async () => {
                  setDialog("settings");
                  setDiagnostics(await api("/diagnostics"));
                }}
              >
                <Settings size={16} />
                <span>模型与工作台设置</span>
                <ChevronRight size={14} />
              </button>
            </div>
            <p className="home-footnote">
              <Folder size={13} />
              项目与研究记录保存在本机
            </p>
          </div>
        ) : (
          <>
            <div className="project-heading">
              <div>
                <div className="eyebrow">
                  项目 <span> / </span> {selected.slice(-6).toUpperCase()}
                </div>
                <h1>{project.title}</h1>
                <p>{project.goal}</p>
              </div>
              <div className="project-heading-actions">
                <button
                  className="button secondary"
                  onClick={() => setDialog("report")}
                >
                  <Download size={14} />
                  导出报告
                </button>
                <button
                  className="icon-button"
                  title={project.archived ? "恢复项目" : "归档项目"}
                  onClick={() =>
                    act(
                      () => api(`/projects/${selected}/archive`, "POST"),
                      project.archived ? "项目已恢复" : "项目已归档",
                    )
                  }
                >
                  <Archive size={16} />
                </button>
              </div>
            </div>
            <div className="workspace-tabs">
              <div>
                {tabs.map(([id, label, Icon]) => (
                  <button
                    key={id}
                    className={tab === id ? "active" : ""}
                    onClick={() => {
                      setTab(id);
                      setInspected(null);
                    }}
                  >
                    <Icon size={15} />
                    {label}
                    {id === "findings" && detail.findings.length > 0 && (
                      <small>{detail.findings.length}</small>
                    )}
                  </button>
                ))}
              </div>
              <span className="workspace-stats">
                {detail.graph.filter((n: Row) => n.kind === "fact").length} 事实
                <span>·</span>
                {
                  detail.findings.filter((f: Row) => f.status === "confirmed")
                    .length
                }{" "}
                已确认发现
              </span>
            </div>
            <section className="workspace-content">
              {tab === "activity" && (
                <>
                  <div className="run-toolbar">
                    <select
                      aria-label="选择任务"
                      value={selectedRun}
                      onChange={(e) => setSelectedRun(e.target.value)}
                    >
                      <option value="">所有任务</option>
                      {detail.runs.map((r: Row) => (
                        <option key={r.id} value={r.id}>
                          {stamp(r.created_at)} · {r.prompt.slice(0, 28)}
                        </option>
                      ))}
                    </select>
                    <input
                      aria-label="搜索活动"
                      placeholder="筛选活动记录…"
                      value={logQuery}
                      onChange={(e) => setLogQuery(e.target.value)}
                    />
                    {currentRun && <Status value={currentRun.status} />}
                  </div>
                  <ActivityFeed
                    events={displayEvents}
                    runs={detail.runs}
                    onSelect={(r) => {
                      setInspected({ ...r, kind: "run" });
                      setRightOpen(true);
                    }}
                  />
                </>
              )}
              {tab === "graph" && (
                <Graph
                  nodes={detail.graph}
                  onSelect={(n) => {
                    setInspected({ ...n, inspectType: "node" });
                    setRightOpen(true);
                  }}
                />
              )}
              {tab === "findings" && (
                <div className="collection">
                  <div className="collection-heading">
                    <div>
                      <h2>研究发现</h2>
                      <p>区分模型判断与人工确认，让结论经得起复核。</p>
                    </div>
                    <button
                      className="button secondary"
                      onClick={() => openFinding()}
                    >
                      <Plus size={14} />
                      记录发现
                    </button>
                  </div>
                  {!detail.findings.length ? (
                    <Empty
                      icon={<ShieldCheck />}
                      title="还没有记录发现"
                      text="把研究中的线索整理为发现，关联证据后再确认。"
                      action="记录第一条发现"
                      onAction={() => openFinding()}
                    />
                  ) : (
                    <div className="finding-list">
                      {detail.findings.map((f: Row) => (
                        <button
                          key={f.id}
                          className="finding-card"
                          onClick={() => {
                            setInspected({ ...f, inspectType: "finding" });
                            setRightOpen(true);
                          }}
                        >
                          <span className={"severity " + f.severity}>
                            {severity[f.severity]}
                          </span>
                          <div>
                            <h3>{f.title}</h3>
                            <p>
                              {f.description.slice(0, 120) || "尚未填写说明"}
                            </p>
                            <small>
                              {parse(f.evidence).length} 项证据 ·{" "}
                              {stamp(f.created_at)}
                            </small>
                          </div>
                          <span className={"finding-state " + f.status}>
                            {
                              (
                                {
                                  draft: "草稿",
                                  review: "待复核",
                                  confirmed: "已确认",
                                  dismissed: "已排除",
                                } as Row
                              )[f.status]
                            }
                          </span>
                          <ChevronRight size={15} />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {tab === "requests" && (
                <div className="collection">
                  <div className="collection-heading">
                    <div>
                      <h2>请求与响应</h2>
                      <p>从 HAR 或 OpenAPI 开始，每次重放都需要你的确认。</p>
                    </div>
                    <div className="inline-actions">
                      <button
                        className="button secondary"
                        onClick={() => setDialog("identities")}
                      >
                        身份配置
                      </button>
                      <button
                        className="button secondary"
                        onClick={() => importRef.current?.click()}
                      >
                        导入接口
                      </button>
                      <button
                        className="button secondary"
                        onClick={() => setDialog("request")}
                      >
                        <Plus size={14} />
                        新建请求
                      </button>
                    </div>
                  </div>
                  {!detail.requests.length ? (
                    <Empty
                      icon={<Globe />}
                      title="把接口上下文带进工作台"
                      text="导入 HAR 或 OpenAPI JSON；导入时移除 Cookie 与 Authorization。"
                      action="导入接口文件"
                      onAction={() => importRef.current?.click()}
                    />
                  ) : (
                    <div className="request-list">
                      {detail.requests.map((r: Row) => (
                        <button
                          key={r.id}
                          className="request-row"
                          onClick={() => {
                            setInspected({ ...r, inspectType: "request" });
                            setRightOpen(true);
                          }}
                        >
                          <span className={"method " + r.method}>
                            {r.method}
                          </span>
                          <code>{r.url}</code>
                          {r.response && (
                            <span className="response-code">
                              {parse(r.response, {}).status}
                            </span>
                          )}
                          <ChevronRight size={14} />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {tab === "artifacts" && (
                <div className="collection">
                  <div className="collection-heading">
                    <div>
                      <h2>证据与产物</h2>
                      <p>文件与运行记录关联，保留 SHA-256 校验值。</p>
                    </div>
                    <button
                      className="button secondary"
                      onClick={() => uploadRef.current?.click()}
                    >
                      <Paperclip size={14} />
                      添加证据
                    </button>
                  </div>
                  {!detail.artifacts.length ? (
                    <Empty
                      icon={<Layers />}
                      title="给你的发现留下依据"
                      text="上传请求记录、日志、截图或研究文件，单文件最大 8 MiB。"
                      action="添加证据文件"
                      onAction={() => uploadRef.current?.click()}
                    />
                  ) : (
                    <div className="artifact-grid">
                      {detail.artifacts.map((a: Row) => (
                        <button
                          className="artifact-card"
                          key={a.id}
                          onClick={() => {
                            setInspected({ ...a, inspectType: "artifact" });
                            setRightOpen(true);
                          }}
                        >
                          <FileText size={25} />
                          <h3>{a.name}</h3>
                          <p>
                            {(a.size / 1024).toFixed(1)} KB ·{" "}
                            {stamp(a.created_at)}
                          </p>
                          <small>SHA-256 {a.sha256.slice(0, 12)}…</small>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {tab === "terminal" && (
                <React.Suspense
                  fallback={<div className="empty">正在加载终端…</div>}
                >
                  <ProjectTerminal projectId={selected} />
                </React.Suspense>
              )}
            </section>
            {overview.approvals.some((a: Row) => a.project_id === selected) && (
              <button
                className="approval-banner"
                onClick={() => setDialog("approvals")}
              >
                <ShieldCheck size={16} />
                <span>有操作正在等待确认，执行已暂停。</span>查看详情
                <ArrowUpRight size={14} />
              </button>
            )}
            <div className="composer-area">
              <div className="composer-box">
                <textarea
                  aria-label="任务输入"
                  placeholder={
                    activeRun
                      ? "补充上下文或调整下一步方向…"
                      : "描述研究目标，或开始一次新的探索…"
                  }
                  value={composer}
                  onChange={(e) => setComposer(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault();
                      send();
                    }
                  }}
                />
                <div className="composer-controls">
                  <div>
                    <button
                      className="icon-button"
                      title="添加附件"
                      onClick={() => uploadRef.current?.click()}
                    >
                      <Paperclip size={17} />
                    </button>
                    <span className="composer-model">
                      <span className="model-symbol">D</span>DeepSeek V4.1 Flash
                      <small>Free</small>
                    </span>
                  </div>
                  <div>
                    {activeRun && (
                      <button
                        className="stop-button"
                        aria-label="停止任务"
                        onClick={() =>
                          act(
                            () => api(`/runs/${activeRun.id}/stop`, "POST"),
                            "任务已停止",
                          )
                        }
                      >
                        <Square size={12} />
                        停止
                      </button>
                    )}
                    <button
                      className="send-button"
                      aria-label={activeRun ? "发送引导" : "开始探索"}
                      disabled={busy || !composer.trim() || !!project.archived}
                      onClick={send}
                    >
                      <ArrowUp size={18} />
                    </button>
                  </div>
                </div>
              </div>
              <div className="composer-note">
                <span>
                  {activeRun
                    ? "引导将在下一个探索决策阶段读取"
                    : "Ctrl + Enter 发送"}
                  <span>·</span>关键操作逐次确认
                </span>
                <span>研究结果需人工复核</span>
              </div>
            </div>
          </>
        )}
        <footer className="statusbar">
          <span>
            {connected ? <Wifi size={12} /> : <WifiOff size={12} />}{" "}
            {connected ? "已连接本地引擎" : "正在重新连接"}
          </span>
          <span>
            {activeRun
              ? `${statuses[activeRun.status]} · ${Math.max(0, Math.floor((elapsed - new Date(activeRun.created_at).getTime()) / 60000))} 分钟`
              : "所有记录保存在本机"}
            <span>·</span>v0.1.1-preview
          </span>
        </footer>
      </main>
      <aside className="inspector">
        <div
          className="resize-handle right"
          onPointerDown={(e) => resize("right", e)}
        />
        <div className="inspector-title">
          <span>
            {inspected?.inspectType === "finding"
              ? "发现详情"
              : inspected?.inspectType === "request"
                ? "请求详情"
                : inspected?.inspectType === "artifact"
                  ? "产物详情"
                  : inspected?.inspectType === "node"
                    ? "节点详情"
                    : "项目上下文"}
          </span>
          <button
            className="icon-button"
            aria-label="关闭详情"
            onClick={() => setRightOpen(false)}
          >
            <PanelRightClose size={16} />
          </button>
        </div>
        <div className="inspector-body">
          {inspected?.inspectType === "finding" ? (
            <>
              <span className={"severity " + inspected.severity}>
                {severity[inspected.severity]}
              </span>
              <h2>{inspected.title}</h2>
              <Prose text={inspected.description} />
              <h4>复现步骤</h4>
              <Prose text={inspected.reproduction || "尚未填写"} />
              <h4>影响</h4>
              <Prose text={inspected.impact || "尚未填写"} />
              <h4>关联证据</h4>
              {parse(inspected.evidence).map((id: string) => (
                <a
                  className="artifact-link"
                  href={"/api/v2/artifacts/" + id}
                  key={id}
                >
                  <FileText size={14} />
                  {detail?.artifacts.find((a: Row) => a.id === id)?.name || id}
                </a>
              ))}
              <button
                className="button secondary full"
                onClick={() => openFinding(inspected)}
              >
                编辑与复核
              </button>
            </>
          ) : inspected?.inspectType === "request" ? (
            <>
              <span className={"method " + inspected.method}>
                {inspected.method}
              </span>
              <h3 className="break-all">{inspected.url}</h3>
              <h4>请求头</h4>
              <pre>{JSON.stringify(parse(inspected.headers, {}), null, 2)}</pre>
              <h4>请求体</h4>
              <pre>{inspected.body || "无请求体"}</pre>
              <button
                className="button primary full"
                onClick={() =>
                  act(
                    () => api(`/requests/${inspected.id}/replay`, "POST"),
                    "重放已进入待确认队列",
                  )
                }
              >
                <ShieldCheck size={14} />
                申请重放
              </button>
              {inspected.response && (
                <>
                  <h4>响应</h4>
                  <pre>
                    {JSON.stringify(parse(inspected.response, {}), null, 2)}
                  </pre>
                </>
              )}
            </>
          ) : inspected?.inspectType === "artifact" ? (
            <>
              <FileText size={28} />
              <h2>{inspected.name}</h2>
              <h4>SHA-256</h4>
              <code className="break-all">{inspected.sha256}</code>
              <h4>关联运行</h4>
              <code>{inspected.run_id || "人工上传"}</code>
              <a
                className="button secondary full"
                href={"/api/v2/artifacts/" + inspected.id}
              >
                <Download size={14} />
                下载原始证据
              </a>
            </>
          ) : inspected?.inspectType === "node" ? (
            <>
              <span className="tag">{inspected.kind}</span>
              <h4>节点内容</h4>
              <Prose text={inspected.description} />
              <h4>来源节点</h4>
              <code className="break-all">
                {parse(inspected.sources).join("\n") || "起始节点"}
              </code>
            </>
          ) : project ? (
            <>
              <div className="inspector-section">
                <div className="section-eyebrow">
                  <Folder size={14} />
                  研究项目
                </div>
                <h2>{project.title}</h2>
                <p className="muted">从已知起点，向清晰目标探索。</p>
              </div>
              <div className="inspector-section">
                <h4>
                  <span className="node-dot origin" />
                  起点
                </h4>
                <p>{project.origin}</p>
                <h4>
                  <span className="node-dot goal" />
                  目标
                </h4>
                <p>{project.goal}</p>
              </div>
              <div className="inspector-section">
                <h4>允许范围</h4>
                {parse(project.scope).length ? (
                  parse(project.scope).map((s: string) => (
                    <code className="scope-item" key={s}>
                      {s}
                    </code>
                  ))
                ) : (
                  <p className="muted">尚未设置 HTTP 重放范围</p>
                )}
                <h4>排除项</h4>
                {parse(project.excluded).length ? (
                  parse(project.excluded).map((s: string) => (
                    <code className="scope-item" key={s}>
                      {s}
                    </code>
                  ))
                ) : (
                  <p className="muted">无排除项</p>
                )}
              </div>
              {inspectedRun && (
                <div className="inspector-section">
                  <h4>当前任务</h4>
                  <Status value={inspectedRun.status} />
                  <dl>
                    <dt>探索轮数</dt>
                    <dd>
                      {inspectedRun.step} / {inspectedRun.max_steps}
                    </dd>
                    <dt>累计 Token</dt>
                    <dd>{Number(inspectedRun.tokens).toLocaleString()}</dd>
                    <dt>费用</dt>
                    <dd>${Number(inspectedRun.cost).toFixed(4)}</dd>
                  </dl>
                  {inspectedRun.error && (
                    <div className="error-detail">{inspectedRun.error}</div>
                  )}
                  {!LIVE.includes(inspectedRun.status) && (
                    <button
                      className="button secondary full"
                      onClick={() => {
                        setComposer(inspectedRun.prompt);
                        notify("任务已放入输入框，复核后发送以创建新尝试");
                      }}
                    >
                      <RefreshCw size={14} />
                      继续新的尝试
                    </button>
                  )}
                </div>
              )}
              <div className="inspector-footnote">
                <ShieldCheck size={16} />
                <p>关键操作逐次确认。执行环境沿用当前用户权限。</p>
              </div>
            </>
          ) : (
            <div className="inspector-placeholder">
              <GitBranch size={30} />
              <h3>研究上下文</h3>
              <p>
                选择项目、图谱节点或发现，
                <br />
                在这里查看详情。
              </p>
            </div>
          )}
        </div>
      </aside>
      <input
        ref={uploadRef}
        type="file"
        hidden
        onChange={(e) => {
          if (e.target.files?.[0]) upload(e.target.files[0]);
          e.target.value = "";
        }}
      />
      <input
        ref={importRef}
        type="file"
        accept=".json,.har"
        hidden
        onChange={(e) => {
          if (e.target.files?.[0]) importFile(e.target.files[0]);
          e.target.value = "";
        }}
      />
      <Modal
        open={dialog === "project"}
        onClose={() => setDialog("")}
        title="新建研究项目"
        description="先确定起点、目标和范围，让探索有清晰边界。"
      >
        <form onSubmit={createProject}>
          <label>
            项目名称
            <input
              autoFocus
              placeholder="例如：Atlas API 授权评估"
              required
              value={projectForm.title}
              onChange={(e) =>
                setProjectForm({ ...projectForm, title: e.target.value })
              }
            />
          </label>
          <label>
            起点
            <textarea
              required
              placeholder="已知目标、环境、已有信息…"
              value={projectForm.origin}
              onChange={(e) =>
                setProjectForm({ ...projectForm, origin: e.target.value })
              }
            />
          </label>
          <label>
            研究目标
            <textarea
              required
              placeholder="明确的完成条件…"
              value={projectForm.goal}
              onChange={(e) =>
                setProjectForm({ ...projectForm, goal: e.target.value })
              }
            />
          </label>
          <div className="form-grid">
            <label>
              允许的 HTTP 范围
              <textarea
                placeholder={"https://example.com/api\n每行一个完整 URL 前缀"}
                value={projectForm.scope}
                onChange={(e) =>
                  setProjectForm({ ...projectForm, scope: e.target.value })
                }
              />
            </label>
            <label>
              排除范围
              <textarea
                placeholder="https://example.com/api/admin"
                value={projectForm.excluded}
                onChange={(e) =>
                  setProjectForm({ ...projectForm, excluded: e.target.value })
                }
              />
            </label>
          </div>
          <div className="form-actions">
            <button
              type="button"
              className="button secondary"
              onClick={() => setDialog("")}
            >
              取消
            </button>
            <button className="button primary" disabled={busy}>
              创建项目
              <ArrowUpRight size={14} />
            </button>
          </div>
        </form>
      </Modal>
      <Modal
        open={dialog === "finding"}
        onClose={() => setDialog("")}
        title={editingFinding ? "编辑与复核发现" : "记录研究发现"}
        description="已确认发现必须关联证据，并填写可复现的步骤。"
        wide
      >
        <form onSubmit={saveFinding}>
          <label>
            发现标题
            <input
              required
              value={findingForm.title}
              onChange={(e) =>
                setFindingForm({ ...findingForm, title: e.target.value })
              }
            />
          </label>
          <div className="form-grid">
            <label>
              严重程度
              <select
                value={findingForm.severity}
                onChange={(e) =>
                  setFindingForm({ ...findingForm, severity: e.target.value })
                }
              >
                {Object.entries(severity).map(([k, v]) => (
                  <option value={k} key={k}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
            <label>
              复核状态
              <select
                value={findingForm.status}
                onChange={(e) =>
                  setFindingForm({ ...findingForm, status: e.target.value })
                }
              >
                <option value="draft">草稿</option>
                <option value="review">待复核</option>
                <option value="confirmed">已人工确认</option>
                <option value="dismissed">已排除</option>
              </select>
            </label>
          </div>
          {(["description", "reproduction", "impact"] as const).map(
            (key, i) => (
              <label key={key}>
                {["说明", "复现步骤", "影响"][i]}
                <textarea
                  value={findingForm[key]}
                  onChange={(e) =>
                    setFindingForm({ ...findingForm, [key]: e.target.value })
                  }
                />
              </label>
            ),
          )}
          <label>关联证据</label>
          <div className="evidence-picker">
            {detail?.artifacts.map((a: Row) => (
              <label key={a.id} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={findingForm.evidence.includes(a.id)}
                  onChange={(e) =>
                    setFindingForm({
                      ...findingForm,
                      evidence: e.target.checked
                        ? [...findingForm.evidence, a.id]
                        : findingForm.evidence.filter((id) => id !== a.id),
                    })
                  }
                />
                {a.name}
              </label>
            ))}
            {!detail?.artifacts.length && (
              <p className="muted">先在「产物」中添加证据文件。</p>
            )}
          </div>
          <div className="form-actions">
            <button className="button primary" disabled={busy}>
              保存发现
            </button>
          </div>
        </form>
      </Modal>
      <Modal
        open={dialog === "identities"}
        onClose={() => setDialog("")}
        title="项目身份配置"
        description="敏感请求头加密存储在本机，界面不会重新显示明文。身份只用于你批准的 HTTP 重放。"
      >
        <div className="identity-list">
          {detail?.identities?.map((i: Row) => (
            <div key={i.id}>
              <span>
                <b>{i.name}</b>
                <small>{parse(i.header_names).join(", ")}</small>
              </span>
              <button
                className="icon-button"
                aria-label={"删除身份 " + i.name}
                onClick={() =>
                  act(() => api("/identities/" + i.id, "DELETE"), "身份已删除")
                }
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              const headers = JSON.parse(identityForm.headers);
              if (
                await act(
                  () =>
                    api(`/projects/${selected}/identities`, "POST", {
                      name: identityForm.name,
                      headers,
                    }),
                  "身份已加密保存",
                )
              )
                setIdentityForm({ name: "", headers: "{}" });
            } catch {
              notify("请求头必须是 JSON 对象", true);
            }
          }}
        >
          <label>
            身份名称
            <input
              required
              value={identityForm.name}
              onChange={(e) =>
                setIdentityForm({ ...identityForm, name: e.target.value })
              }
              placeholder="例如：测试账号 A"
            />
          </label>
          <label>
            敏感请求头 JSON
            <textarea
              className="mono"
              autoComplete="off"
              value={identityForm.headers}
              onChange={(e) =>
                setIdentityForm({ ...identityForm, headers: e.target.value })
              }
            />
          </label>
          <div className="form-actions">
            <button className="button primary">加密保存身份</button>
          </div>
        </form>
      </Modal>
      <Modal
        open={dialog === "request"}
        onClose={() => setDialog("")}
        title="新建 HTTP 请求"
        description="请求保存后可以申请重放；范围和参数将在审批前再次检查。"
      >
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              const headers = JSON.parse(requestForm.headers);
              if (
                await act(
                  () =>
                    api(`/projects/${selected}/requests`, "POST", {
                      ...requestForm,
                      headers,
                      identity_id: requestForm.identity_id || null,
                    }),
                  "请求已保存",
                )
              ) {
                setDialog("");
                setRequestForm({
                  method: "GET",
                  url: "",
                  headers: "{}",
                  body: "",
                  identity_id: "",
                });
              }
            } catch {
              notify("请求头必须是 JSON 对象", true);
            }
          }}
        >
          <div className="form-grid request-inputs">
            <label>
              方法
              <select
                value={requestForm.method}
                onChange={(e) =>
                  setRequestForm({ ...requestForm, method: e.target.value })
                }
              >
                {[
                  "GET",
                  "HEAD",
                  "POST",
                  "PUT",
                  "PATCH",
                  "DELETE",
                  "OPTIONS",
                ].map((m) => (
                  <option key={m}>{m}</option>
                ))}
              </select>
            </label>
            <label>
              URL
              <input
                type="url"
                required
                value={requestForm.url}
                onChange={(e) =>
                  setRequestForm({ ...requestForm, url: e.target.value })
                }
                placeholder="https://example.com/api"
              />
            </label>
          </div>
          <label>
            请求身份
            <select
              value={requestForm.identity_id}
              onChange={(e) =>
                setRequestForm({ ...requestForm, identity_id: e.target.value })
              }
            >
              <option value="">不附加身份</option>
              {detail?.identities?.map((i: Row) => (
                <option key={i.id} value={i.id}>
                  {i.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            请求头 JSON（敏感值请使用身份配置）
            <textarea
              className="mono"
              value={requestForm.headers}
              onChange={(e) =>
                setRequestForm({ ...requestForm, headers: e.target.value })
              }
            />
          </label>
          <label>
            请求体
            <textarea
              className="mono"
              value={requestForm.body}
              onChange={(e) =>
                setRequestForm({ ...requestForm, body: e.target.value })
              }
            />
          </label>
          <div className="form-actions">
            <button className="button primary">保存请求</button>
          </div>
        </form>
      </Modal>
      <Modal
        open={dialog === "approvals"}
        onClose={() => setDialog("")}
        title="待我确认"
        description="批准只对本次操作有效。拒绝后不会执行该操作。"
        wide
      >
        {overview.approvals.length ? (
          overview.approvals.map((a: Row) => (
            <div className="approval-card" key={a.id}>
              <div>
                <span className="tag amber">{a.permission}</span>
                <small>
                  {
                    overview.projects.find((p: Row) => p.id === a.project_id)
                      ?.title
                  }
                </small>
              </div>
              <pre>{JSON.stringify(parse(a.details, {}), null, 2)}</pre>
              <div className="form-actions">
                <button
                  className="button secondary"
                  disabled={busy}
                  onClick={() =>
                    act(
                      () =>
                        api("/approvals/" + a.id, "POST", {
                          decision: "reject",
                        }),
                      "已拒绝本次操作",
                    )
                  }
                >
                  <X size={14} />
                  拒绝
                </button>
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={() =>
                    act(
                      () =>
                        api("/approvals/" + a.id, "POST", { decision: "once" }),
                      "已批准本次操作",
                    )
                  }
                >
                  <Check size={14} />
                  批准本次
                </button>
              </div>
            </div>
          ))
        ) : (
          <Empty
            icon={<ShieldCheck />}
            title="目前没有待确认操作"
            text="执行中的关键操作会在这里等待你的决定。"
          />
        )}
      </Modal>
      <Modal
        open={dialog === "settings"}
        onClose={() => setDialog("")}
        title="设置与诊断"
        description="模型、执行环境和工作台状态。"
        wide
      >
        <div className="settings-section">
          <h3>外观</h3>
          <div className="theme-options">
            {[
              ["system", "跟随系统", Monitor],
              ["light", "浅色", Sun],
              ["dark", "深色", Moon],
            ].map(([value, label, Icon]: any) => (
              <button
                key={value}
                className={theme === value ? "selected" : ""}
                onClick={() => setTheme(value)}
              >
                <Icon size={19} />
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="settings-section">
          <h3>执行环境</h3>
          {diagnostics ? (
            <dl className="diagnostic-list">
              {Object.entries(diagnostics).map(([key, value]) => (
                <React.Fragment key={key}>
                  <dt>
                    {(
                      {
                        version: "版本",
                        platform: "平台",
                        model: "默认模型",
                        opencode_available: "OpenCode 可用",
                        active_runs: "活动会话",
                        database: "数据库",
                        schema_version: "数据结构版本",
                        execution: "执行环境",
                        approval: "审批策略",
                        paid_fallback: "付费回退",
                      } as Row
                    )[key] || key}
                  </dt>
                  <dd>
                    {typeof value === "boolean"
                      ? value
                        ? "是"
                        : "否"
                      : String(value)}
                  </dd>
                </React.Fragment>
              ))}
            </dl>
          ) : (
            <p>正在读取诊断…</p>
          )}
          <div className="inline-notice">
            免费模型额度由服务商控制。额度不足时任务暂停，不会自动切换到付费模型。
          </div>
        </div>
        <div className="settings-section">
          <h3>OpenCode 模型连接</h3>
          <p className="muted">
            {providerInfo?.configured
              ? providerInfo.source === "workbench"
                ? "使用工作台加密保存的凭据"
                : "复用本机已有 OpenCode 登录"
              : "尚未配置 OpenCode 凭据"}
          </p>
          <label className="network-label">
            OpenCode API Key
            <input
              type="password"
              autoComplete="off"
              placeholder="保存后不再显示明文，仅用于免费型号"
              value={providerKey}
              onChange={(e) => setProviderKey(e.target.value)}
            />
          </label>
          <div className="inline-actions" style={{ marginTop: 12 }}>
            <button
              className="button secondary"
              disabled={busy || providerKey.length < 10}
              onClick={async () => {
                if (
                  await act(
                    () =>
                      api("/settings/provider", "PUT", { key: providerKey }),
                    "凭据已加密保存，新的执行会话生效",
                  )
                ) {
                  setProviderKey("");
                  setProviderInfo(await api("/settings/provider"));
                }
              }}
            >
              加密保存连接
            </button>
            {providerInfo?.source === "workbench" && (
              <button
                className="button secondary"
                onClick={async () => {
                  if (
                    await act(
                      () => api("/settings/provider", "DELETE"),
                      "已移除工作台凭据",
                    )
                  )
                    setProviderInfo(await api("/settings/provider"));
                }}
              >
                恢复本机 OpenCode 登录
              </button>
            )}
          </div>
        </div>
        <div className="settings-section">
          <h3>模型网络代理</h3>
          <label className="network-label">
            HTTP / HTTPS 代理
            <input
              placeholder="留空直连，例如 http://127.0.0.1:7897"
              value={proxyURL}
              onChange={(e) => setProxyURL(e.target.value)}
            />
          </label>
          <p className="muted">
            仅用于新启动的 OpenCode 会话。本地服务与 HTTP 重放保持直接连接。
          </p>
          <button
            className="button secondary"
            onClick={() =>
              act(
                () => api("/settings/network", "PUT", { proxy: proxyURL }),
                "网络设置已保存，对新执行会话生效",
              )
            }
          >
            保存网络设置
          </button>
        </div>
        <div className="settings-section">
          <h3>通知与数据</h3>
          <div className="inline-actions">
            <button
              className="button secondary"
              onClick={() => {
                "Notification" in window
                  ? Notification.requestPermission().then((p) =>
                      notify(
                        p === "granted" ? "桌面通知已开启" : "通知权限未开启",
                      ),
                    )
                  : notify("此环境不支持桌面通知");
              }}
            >
              开启桌面通知
            </button>
            <button
              className="button secondary"
              onClick={() =>
                act(
                  () => api("/backup", "POST"),
                  "数据库备份已保存；证据文件需一并备份项目目录",
                )
              }
            >
              备份数据库
            </button>
            <a className="button secondary" href="/api/v2/diagnostics/export">
              导出脱敏诊断
            </a>
          </div>
        </div>
      </Modal>
      <Modal
        open={dialog === "report"}
        onClose={() => setDialog("")}
        title="导出研究报告"
        description="仅包含已人工确认的发现；导出前请检查脱敏内容。"
      >
        <p className="muted">
          本项目共有{" "}
          {detail?.findings.filter((f: Row) => f.status === "confirmed")
            .length || 0}{" "}
          项已确认发现。报告将保留证据名称、校验值和关联运行。
        </p>
        <div className="report-actions">
          <a
            className="button secondary"
            href={`/api/v2/projects/${selected}/report`}
          >
            <FileText size={17} />
            Markdown
          </a>
          <a
            className="button secondary"
            href={`/api/v2/projects/${selected}/report?format=html`}
          >
            <Globe size={17} />
            HTML
          </a>
          <a
            className="button secondary"
            href={`/api/v2/projects/${selected}/report?format=pdf`}
          >
            <Download size={17} />
            PDF
          </a>
        </div>
        <button
          className="text-button"
          onClick={async () => {
            const text = await (
              await fetch(`/api/v2/projects/${selected}/report`)
            ).text();
            setInspected({
              inspectType: "node",
              kind: "report",
              description: text,
              sources: "[]",
            });
            setRightOpen(true);
            setDialog("");
          }}
        >
          先预览脱敏内容
          <ArrowUpRight size={13} />
        </button>
      </Modal>
      <Modal
        open={dialog === "search"}
        onClose={() => setDialog("")}
        title="搜索与命令"
        description="快速切换项目或执行工作台操作。"
      >
        <div className="command-input">
          <Search size={18} />
          <input
            autoFocus
            placeholder="搜索项目，或输入命令…"
            value={command}
            onChange={(e) => setCommand(e.target.value)}
          />
          <kbd>ESC</kbd>
        </div>
        <div className="command-results">
          {overview.projects
            .filter((p: Row) =>
              p.title.toLowerCase().includes(command.toLowerCase()),
            )
            .map((p: Row) => (
              <button key={p.id} onClick={() => choose(p.id)}>
                <Folder size={16} />
                {p.title}
                <ArrowUpRight size={14} />
              </button>
            ))}
          {[
            ["新建研究项目", "project"],
            ["待我确认", "approvals"],
            ["设置与诊断", "settings"],
            ["使用帮助", "help"],
          ]
            .filter(([label]) => !command || label.includes(command))
            .map(([label, d]) => (
              <button
                key={d}
                onClick={() => {
                  setDialog(d);
                  if (d === "settings")
                    api("/diagnostics").then(setDiagnostics);
                }}
              >
                <Command size={16} />
                {label}
                <ChevronRight size={14} />
              </button>
            ))}
        </div>
      </Modal>
      <Modal
        open={dialog === "help"}
        onClose={() => setDialog("")}
        title="欢迎使用 Cairn Workbench"
        description="清晰的目标、可控的过程、可复核的结果。"
      >
        <div className="help-steps">
          {[
            ["01", "创建项目", "设置已知起点、完成目标和 HTTP 范围。"],
            ["02", "发起探索", "在底部输入任务。关键操作暂停等待你确认。"],
            ["03", "补充引导", "执行中发送 Hint，在下一次探索决策时读取。"],
            ["04", "复核与整理", "上传证据、记录发现，人工确认后导出报告。"],
          ].map(([n, t, d]) => (
            <div key={n}>
              <span>{n}</span>
              <section>
                <h3>{t}</h3>
                <p>{d}</p>
              </section>
            </div>
          ))}
        </div>
        <div className="inline-notice">
          Ctrl+K 打开命令面板，Ctrl+Enter
          发送任务。停止不会撤销已经发生的外部修改。
        </div>
      </Modal>
      {toast && (
        <div role="alert" className={"toast " + (toast.error ? "error" : "")}>
          <span>
            {toast.error ? <AlertTriangle size={16} /> : <Check size={16} />}
          </span>
          {toast.text}
          <button
            className="icon-button"
            aria-label="关闭提示"
            onClick={() => setToast(null)}
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

function Empty({
  icon,
  title,
  text,
  action,
  onAction,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
  action?: string;
  onAction?: () => void;
}) {
  return (
    <div className="empty">
      <div>{icon}</div>
      <h3>{title}</h3>
      <p>{text}</p>
      {action && (
        <button className="button secondary" onClick={onAction}>
          {action}
          <ArrowUpRight size={14} />
        </button>
      )}
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
