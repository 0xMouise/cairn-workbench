import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests",
  outputDir: "test-results",
  workers: 1,
  timeout: 30000,
  use: {
    channel: process.env.CI ? undefined : "msedge",
    baseURL: "http://127.0.0.1:18100",
    viewport: { width: 1512, height: 982 },
    trace: "retain-on-failure",
  },
  reporter: [["list"], ["html", { open: "never" }]],
});
