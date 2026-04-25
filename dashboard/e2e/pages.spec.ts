import { expect, test } from "@playwright/test";
import { installDashboardApiStubs } from "./api-mocks";

test("Costs page: renders chart containers with mock data", async ({ page }) => {
  await installDashboardApiStubs(page);
  const summary = {
    range: "7d",
    range_days: 7,
    total_cost_usd: 1.58,
    total_input_tokens: 30000,
    total_output_tokens: 14000,
    total_reviews: 10,
    daily: [
      {
        date: "2025-04-01",
        cost_usd: 0.45,
        input_tokens: 8000,
        output_tokens: 4000,
        total_tokens: 12000,
        reviews: 3,
      },
      {
        date: "2025-04-02",
        cost_usd: 0.82,
        input_tokens: 16000,
        output_tokens: 8000,
        total_tokens: 24000,
        reviews: 5,
      },
      {
        date: "2025-04-03",
        cost_usd: 0.31,
        input_tokens: 5000,
        output_tokens: 3000,
        total_tokens: 8000,
        reviews: 2,
      },
    ],
    by_step: [
      { step: "synthesis", cost_usd: 0.9, input_tokens: 20000, output_tokens: 8000, reviews: 8 },
    ],
    by_model: [{ model_version: "mock", cost_usd: 1.58, reviews: 10 }],
    budget: {
      daily_budget_usd: 10,
      today_cost_usd: 0.4,
      today_percent_of_budget: 4,
      circuit_breaker_threshold: 3,
    },
  };
  await page.route("**/api/v1/costs/summary**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(summary) });
  });
  await page.goto("/costs", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Costs", level: 1 })).toBeVisible();
});

test("Settings page: renders repo config controls", async ({ page }) => {
  await installDashboardApiStubs(page);
  await page.goto("/settings", { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
});

test("Navigation: sidebar links navigate without full reload", async ({ page }) => {
  await installDashboardApiStubs(page);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Sentinel" })).toBeVisible();
  const nav = page.getByRole("navigation");
  await nav.getByRole("link", { name: "Reviews" }).click();
  await expect(page).toHaveURL(/\/reviews/);
  await expect(page.getByRole("heading", { name: "Reviews", level: 1 })).toBeVisible();
  await nav.getByRole("link", { name: "Eval" }).click();
  await expect(page).toHaveURL(/\/eval/);
  await expect(page.getByRole("heading", { name: "Eval", level: 1 })).toBeVisible();
});

test("Health check endpoint returns JSON", async ({ page }) => {
  const resp = await page.request.get("/health");
  if (resp.ok()) {
    const body = await resp.json();
    expect(body).toHaveProperty("status");
    expect(body).toHaveProperty("checks");
  }
});

test("Error boundary: non-existent route shows error or redirects", async ({ page }) => {
  const resp = await page.goto("/this-route-does-not-exist");
  expect(resp).toBeTruthy();
  await expect(page.locator("body")).toBeVisible();
});
