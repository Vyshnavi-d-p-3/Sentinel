import { expect, test } from "@playwright/test";

const ROUTES: { path: string; heading: string | RegExp }[] = [
  { path: "/", heading: "Sentinel" },
  { path: "/reviews", heading: "Reviews" },
  { path: "/try-review", heading: "Try a review" },
  { path: "/eval", heading: "Eval" },
  { path: "/costs", heading: "Costs" },
  { path: "/prompts", heading: "Prompts" },
  { path: "/feedback", heading: "Feedback" },
  { path: "/settings", heading: "Settings" },
];

for (const { path, heading } of ROUTES) {
  test(`${path} renders primary heading (no full reload errors)`, async ({ page }) => {
    const response = await page.goto(path);
    expect(response, `navigation to ${path}`).toBeTruthy();
    expect(response!.ok() || response!.status() === 304, `HTTP ${response!.status()}`).toBeTruthy();
    await expect(
      page.getByRole("heading", { name: heading, level: 1 }),
    ).toBeVisible({ timeout: 30_000 });
  });
}

test("Eval page: strict/soft controls exist when eval API succeeds", async ({ page }) => {
  await page.route("**/api/v1/eval/runs**", async (route) => {
    const url = route.request().url();
    if (url.includes("/latest")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "e2e-run",
          run_at: "2025-01-15T12:00:00Z",
          source: "db",
          prompt_hash: "abc1234",
          model_version: "mock",
          dataset_version: "v1",
          overall_f1: 0.5,
          overall_precision: 0.5,
          overall_recall: 0.5,
          total_prs_evaluated: 1,
          avg_latency_ms: 100,
          total_cost_usd: 0.01,
          git_commit_sha: "a".repeat(40),
          ci_run_url: null,
          strict: {
            overall_f1: 0.4,
            overall_precision: 0.5,
            overall_recall: 0.33,
            per_category: {
              security: {
                precision: 0.5,
                recall: 0.5,
                f1: 0.5,
                true_positives: 1,
                false_positives: 1,
                false_negatives: 1,
              },
            },
          },
          soft: {
            overall_f1: 0.45,
            overall_precision: 0.5,
            overall_recall: 0.4,
            per_category: {
              security: {
                precision: 0.5,
                recall: 0.5,
                f1: 0.5,
                true_positives: 1,
                false_positives: 1,
                false_negatives: 1,
              },
            },
          },
          clean_pr: { clean_pr_fp_rate: 0.05 },
          per_pr: [],
          notes: null,
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        runs: [
          {
            id: "e2e-run",
            run_at: "2025-01-15T12:00:00Z",
            source: "db",
            prompt_hash: "abc1234",
            model_version: "mock",
            dataset_version: "v1",
            overall_f1: 0.5,
            overall_precision: 0.5,
            overall_recall: 0.5,
            total_prs_evaluated: 1,
            avg_latency_ms: 100,
            total_cost_usd: 0.01,
            git_commit_sha: "a".repeat(40),
            ci_run_url: null,
          },
        ],
        sources: { db: true, disk: false },
      }),
    });
  });
  await page.route("**/api/v1/eval/ablation**", async (route) => {
    await route.fulfill({ status: 404, contentType: "application/json", body: "{}" });
  });

  await page.goto("/eval");
  await expect(
    page.getByRole("heading", { name: "Eval", level: 1, exact: true }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "strict" })).toBeVisible();
  await expect(page.getByRole("button", { name: "soft" })).toBeVisible();
  await expect(page.locator(".recharts-responsive-container").first()).toBeVisible();
});

test("Reviews page: filter controls and table surface", async ({ page }) => {
  await page.route("**/api/v1/reviews**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        reviews: [
          {
            id: "rev-e2e",
            repo_id: "r1",
            repo_name: "e2e/repo",
            pr_number: 1,
            pr_title: "e2e title",
            status: "completed",
            comment_count: 0,
            highest_severity: "high",
            quality_score: 7.0,
            created_at: "2025-01-01T00:00:00Z",
          },
        ],
        total: 1,
        page: 1,
        per_page: 20,
      }),
    });
  });
  await page.goto("/reviews");
  await expect(page.getByLabel(/Severity/i)).toBeVisible();
  await expect(page.getByText("e2e/repo#1")).toBeVisible();
});
