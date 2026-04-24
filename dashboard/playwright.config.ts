import { defineConfig, devices } from "@playwright/test";

/**
 * E2E smoke: build must exist (`next build`); `webServer` runs `next start`.
 * Local: set `CI=` and reuse a dev server if you already have one on :3000.
 */
export default defineConfig({
  testDir: "e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  use: {
    // Port 3005 avoids clashing with a dev server on 3000 during local e2e runs.
    baseURL: "http://127.0.0.1:3005",
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npx next start -H 127.0.0.1 -p 3005",
    url: "http://127.0.0.1:3005",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
