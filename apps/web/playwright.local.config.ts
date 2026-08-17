import { defineConfig } from "@playwright/test";

const apiPort = Number(process.env.SENSEMU_E2E_API_PORT ?? "8001");
const webPort = Number(process.env.SENSEMU_E2E_WEB_PORT ?? "3102");
const apiURL = `http://127.0.0.1:${apiPort}`;
const baseURL = `http://127.0.0.1:${webPort}`;

export default defineConfig({
  testDir: "./e2e",
  testMatch: "local-api-workflow.spec.ts",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    browserName: "chromium",
    channel: process.env.CI ? undefined : "chrome",
    viewport: { width: 1280, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "bash scripts/start-e2e-api.sh",
      url: `${apiURL}/health/live`,
      timeout: 60_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        SENSEMU_E2E_API_PORT: String(apiPort),
        SENSEMU_E2E_WEB_PORT: String(webPort),
      },
    },
    {
      command: `npm run start -- --port ${webPort}`,
      url: baseURL,
      timeout: 30_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        SENSEMU_API_URL: apiURL,
        NEXT_PUBLIC_SENSEMU_API_URL: apiURL,
        SENSEMU_PREVIEW_MODE: "false",
        NEXT_PUBLIC_SENSEMU_PREVIEW_MODE: "false",
      },
    },
  ],
});
