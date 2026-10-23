export type Row = Record<string, any>;
export async function api(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<any> {
  const response = await fetch("/api/v2" + path, {
    method,
    credentials: "same-origin",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const message =
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail || `HTTP ${response.status}`);
    throw Object.assign(new Error(message), { status: response.status });
  }
  return response.json();
}
export const statuses: Record<string, string> = {
  queued: "排队中",
  running: "正在探索",
  awaiting_approval: "等待确认",
  completed: "已完成",
  failed: "执行失败",
  cancelled: "已停止",
  interrupted: "已中断",
  quota_blocked: "免费额度不足",
  stopping: "正在停止",
};
export const parse = (text: any, fallback: any = []) => {
  try {
    return typeof text === "string" ? JSON.parse(text) : (text ?? fallback);
  } catch {
    return fallback;
  }
};
export const stamp = (value: string) =>
  new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
