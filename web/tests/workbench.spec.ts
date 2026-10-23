import { test, expect } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

const token = fs
  .readFileSync(
    process.env.CAIRN_E2E_TOKEN_FILE ||
      path.resolve("../.runtime/dev-data/access-token"),
    "utf8",
  )
  .trim();
test.beforeEach(async ({ page }) => {
  await page.request.post("/api/v2/login", { data: { token } });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "新建研究项目", exact: true }),
  ).toBeVisible();
});
test("project, evidence, finding, scope, report and themes", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.getByRole("button", { name: "新建研究项目", exact: true }).click();
  await page.getByLabel("项目名称").fill("界面验收 · " + Date.now());
  await page
    .getByLabel("起点", { exact: true })
    .fill("本地隔离验收环境，不连接外部目标。");
  await page
    .getByLabel("研究目标")
    .fill("验证证据、复核、报告与请求审批完整闭环。");
  await page.getByLabel("允许的 HTTP 范围").fill("http://127.0.0.1:19876");
  await page.getByRole("button", { name: "创建项目", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "从一个清晰的目标开始" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "产物", exact: true }).click();
  await page
    .locator("input[type=file]")
    .first()
    .setInputFiles({
      name: "evidence.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("local acceptance evidence"),
    });
  await expect(
    page.getByRole("heading", { name: "evidence.txt", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "发现", exact: true }).click();
  await page.getByRole("button", { name: "记录发现", exact: true }).click();
  await page.getByLabel("发现标题").fill("本地验收记录（非真实漏洞）");
  await page.getByLabel("复核状态").selectOption("confirmed");
  await page
    .getByLabel("说明", { exact: true })
    .fill("仅验证本地工作台数据流。");
  await page
    .getByLabel("复现步骤")
    .fill("1. 创建项目\n2. 添加证据\n3. 关联并确认发现");
  await page.getByLabel("影响", { exact: true }).fill("无外部系统影响。");
  await page.getByLabel("evidence.txt").check();
  await page.getByRole("button", { name: "保存发现" }).click();
  await expect(
    page.getByRole("heading", { name: "本地验收记录（非真实漏洞）" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "导出报告" }).click();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "Markdown", exact: true }).click(),
  ]);
  const file = await download.path();
  expect(fs.readFileSync(file!, "utf8")).toContain("evidence.txt");
  const [pdfDownload] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("link", { name: "PDF", exact: true }).click(),
  ]);
  const pdfFile = await pdfDownload.path();
  expect(fs.readFileSync(pdfFile!).subarray(0, 5).toString()).toBe("%PDF-");
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("button", { name: "请求", exact: true }).click();
  await page.getByRole("button", { name: "新建请求", exact: true }).click();
  await page
    .getByLabel("URL", { exact: true })
    .fill("http://127.0.0.1:19876/api/health");
  await page.getByRole("button", { name: "保存请求" }).click();
  await page.getByRole("button", { name: /GET http:\/\/127/ }).click();
  await page.getByRole("button", { name: "申请重放" }).click();
  await page
    .getByRole("button", { name: /待我确认/ })
    .first()
    .click();
  await expect(page.getByText("http_request", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "拒绝", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "目前没有待确认操作" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "关闭", exact: true }).click();
  await page.getByRole("button", { name: "探索图", exact: true }).click();
  await expect(page.locator(".graph-canvas canvas").first()).toBeVisible();
  await page.screenshot({
    path: "test-results/workbench-light.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("button", { name: "切换主题" }).click();
  await page.screenshot({
    path: "test-results/workbench-dark.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1280, height: 800 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/workbench-1280.png",
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
test("keyboard command palette and empty settings", async ({ page }) => {
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByPlaceholder("搜索项目，或输入命令…").fill("设置");
  await page
    .getByRole("button", { name: "设置与诊断", exact: true })
    .last()
    .click();
  await expect(page.getByText("SQLite / WAL", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "深色", exact: true }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
});

test("manual project terminal runs only user-entered commands", async ({
  page,
}) => {
  const diagnostics = await (
    await page.request.get("/api/v2/diagnostics")
  ).json();
  test.skip(
    diagnostics.platform === "nt",
    "Manual terminal requires Linux/WSL",
  );
  const result = await page.request.post("/api/v2/projects", {
    data: {
      title: "手动终端验收",
      origin: "本地项目工作目录",
      goal: "验证手动命令输出",
      scope: [],
    },
  });
  const project = await result.json();
  await page.evaluate(
    (id) => localStorage.setItem("cairn.project", id),
    project.id,
  );
  await page.reload();
  await page.getByRole("button", { name: "终端", exact: true }).click();
  const socketPromise = page.waitForEvent("websocket");
  await page.getByRole("button", { name: "打开手动终端", exact: true }).click();
  const socket = await socketPromise;
  let output = "";
  socket.on("framereceived", (frame) => (output += frame.payload.toString()));
  await expect(page.locator(".xterm-helper-textarea")).toBeVisible();
  await page.locator(".xterm-helper-textarea").focus();
  await page.keyboard.type("printf CAIRN_; printf 'TERMINAL_OK\\n'");
  await page.keyboard.press("Enter");
  await expect.poll(() => output).toContain("CAIRN_TERMINAL_OK");
  await page.getByRole("button", { name: "关闭终端", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "打开手动终端", exact: true }),
  ).toBeVisible();
});
