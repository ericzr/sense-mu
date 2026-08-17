import { defineConfig } from "@playwright/test";

const port = Number(process.env.SENSEMU_E2E_PORT ?? "3101");
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  timeout: 30_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL,
    browserName: "chromium",
    channel: process.env.CI ? undefined : "chrome",
    viewport: { width: 794, height: 767 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `npm run start -- --port ${port}`,
    url: baseURL,
    timeout: 30_000,
    reuseExistingServer: !process.env.CI,
    env: {
      ...process.env,
      SENSEMU_PREVIEW_MODE: "true",
      NEXT_PUBLIC_SENSEMU_PREVIEW_MODE: "true",
    },
  },
});
