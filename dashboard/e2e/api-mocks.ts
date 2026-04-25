import type { Page } from "@playwright/test";

/** Minimal `ConfigResponse` for `/api/v1/config/` so Settings and related pages leave loading. */
const MOCK_CONFIG = {
  version: "0.0.0",
  prompt_hash: "e2e",
  llm: {
    default_model: "claude-sonnet-4-20250514",
    fallback_model: "gpt-4o",
    mock_mode: true,
    has_anthropic_key: false,
    has_openai_key: false,
  },
  cost_guard: {
    daily_token_budget: 100000,
    per_pr_token_cap: 20000,
    circuit_breaker_threshold: 3,
    circuit_breaker_window_sec: 300,
  },
  retrieval: {
    embedding_model: "voyage-code-3",
    embedding_dim: 1024,
    top_k: 5,
    rrf_k: 60,
    per_source_top_k: 20,
    recency_boost_max: 0.1,
    recency_half_life_days: 30,
    context_token_budget: 8000,
    diff_share: 0.5,
    has_voyage_key: false,
  },
  observability: { has_langfuse_keys: false },
  github: {
    app_id_configured: false,
    webhook_secret_configured: false,
    private_key_path: "",
  },
  eval: {
    remote_trigger_enabled: false,
    trigger_force_mock: true,
    trigger_timeout_sec: 600,
  },
  cors_origins: ["http://127.0.0.1:3005"],
};

const MOCK_COST_SUMMARY = {
  range: "7d",
  range_days: 7,
  total_cost_usd: 0,
  total_input_tokens: 0,
  total_output_tokens: 0,
  total_reviews: 0,
  daily: [] as { date: string; cost_usd: number; input_tokens: number; output_tokens: number; total_tokens: number; reviews: number }[],
  by_step: [] as { step: string; cost_usd: number; input_tokens: number; output_tokens: number; reviews: number }[],
  by_model: [] as { model_version: string; cost_usd: number; reviews: number }[],
  budget: {
    daily_budget_usd: null as number | null,
    today_cost_usd: 0,
    today_percent_of_budget: 0,
    circuit_breaker_threshold: 3,
  },
};

const MOCK_FEEDBACK_STATS = {
  window_days: 30,
  total_events: 0,
  resolved: 0,
  dismissed: 0,
  replied: 0,
  thumbs_up: 0,
  thumbs_down: 0,
  agreement_rate: 0,
  by_category: [] as { category: string; count: number }[],
  by_day: [] as { day: string; count: number }[],
  counts_by_action: {} as Record<string, number>,
};

const MOCK_REPOS = {
  repos: [
    {
      id: "r1",
      github_id: 1,
      full_name: "e2e/repo",
      auto_review: true,
      daily_token_budget: 100000,
      per_pr_token_cap: 20000,
    },
  ],
  total: 1,
  page: 1,
  per_page: 50,
};

const MOCK_PROMPTS = {
  active: null,
  prompts: [] as { hash: string; name: string; version: number; description: string | null; is_active: boolean; created_at: string | null; source: "db" | "code" }[],
};

const MOCK_REVIEW_LIST = { reviews: [], total: 0, page: 1, per_page: 20 };

/**
 * Stub backend routes so E2E does not need a live API. Safe to call once per test.
 */
export async function installDashboardApiStubs(page: Page) {
  await page.route("**/api/v1/config/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_CONFIG) });
  });
  await page.route("**/api/v1/repos**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_REPOS) });
  });
  await page.route("**/api/v1/costs/summary**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_COST_SUMMARY) });
  });
  await page.route("**/api/v1/feedback/stats**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_FEEDBACK_STATS) });
  });
  await page.route("**/api/v1/feedback/recent**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
  await page.route("**/api/v1/prompts/**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_PROMPTS) });
  });
  await page.route("**/api/v1/reviews**", async (route) => {
    const u = route.request().url();
    if (u.includes("/preview")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          pr_title: "e2e",
          summary: "e2e",
          pr_quality_score: 7,
          review_focus_areas: [],
          comments: [],
          total_tokens: 0,
          input_tokens: 0,
          output_tokens: 0,
          latency_ms: 0,
        }),
      });
      return;
    }
    if (route.request().method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(MOCK_REVIEW_LIST) });
      return;
    }
    await route.continue();
  });
}
