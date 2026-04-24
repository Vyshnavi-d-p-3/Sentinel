// Shape contracts for the FastAPI backend.
// Keep these in sync with the Pydantic models in backend/app/routers/*.

export type Severity = "critical" | "high" | "medium" | "low";

export type Category =
  | "security"
  | "bug"
  | "performance"
  | "style"
  | "suggestion";

export interface ReviewCommentOut {
  file_path: string;
  line_number: number;
  category: Category | string;
  severity: Severity | string;
  description: string;
  suggestion?: string | null;
  confidence?: number | null;
  related_files?: string[];
}

export interface ReviewListItem {
  id: string;
  repo_id: string;
  repo_name: string | null;
  pr_number: number;
  pr_title: string | null;
  status: string;
  comment_count: number;
  highest_severity: Severity | string | null;
  quality_score: number | null;
  created_at: string | null;
}

export interface ReviewListResponse {
  reviews: ReviewListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface ReviewDetail {
  id: string;
  repo_id: string;
  repo_name: string | null;
  pr_number: number;
  pr_title: string | null;
  pr_url: string | null;
  diff_hash: string | null;
  prompt_hash: string | null;
  model_version: string | null;
  status: string;
  summary: string | null;
  pr_quality_score: number | null;
  review_focus_areas: string[];
  triage_result: Record<string, unknown> | null;
  pipeline_step_timings: Record<string, number> | null;
  comments: ReviewCommentOut[];
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  retrieval_ms: number;
  created_at: string | null;
}

export interface ReviewDetailResponse {
  review: ReviewDetail;
}

// ---- Repos (GitHub App installations) -----------------------------------

export interface Repo {
  id: string;
  github_id: number;
  full_name: string;
  installation_id: number;
  default_branch: string;
  auto_review: boolean;
  daily_token_budget: number;
  per_pr_token_cap: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface RepoListResponse {
  repos: Repo[];
  total: number;
  page: number;
  per_page: number;
}

export interface RepoSettingsPatch {
  default_branch?: string;
  auto_review?: boolean;
  daily_token_budget?: number;
  per_pr_token_cap?: number;
}

// ---- Feedback ------------------------------------------------------------

export interface CategoryStat {
  category: string;
  resolved: number;
  dismissed: number;
  replied: number;
  agreement_rate: number;
  total: number;
}

export interface DayStat {
  date: string;
  resolved: number;
  dismissed: number;
  replied: number;
  agreement_rate: number;
}

export interface FeedbackStats {
  window_days: number;
  total_events: number;
  resolved: number;
  dismissed: number;
  replied: number;
  thumbs_up: number;
  thumbs_down: number;
  agreement_rate: number;
  by_category: CategoryStat[];
  by_day: DayStat[];
  counts_by_action: Record<string, number>;
}

export interface FeedbackEvent {
  id: string;
  review_id: string;
  repo_id: string;
  action: string;
  category: string | null;
  severity: string | null;
  comment_index: number | null;
  github_user: string | null;
  reply_body: string | null;
  created_at: string;
}

// ---- Costs ---------------------------------------------------------------

export interface CostDailyRow {
  date: string;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  reviews: number;
}

export interface CostByStep {
  step: string;
  cost_usd: number;
  input_tokens: number;
  output_tokens: number;
  reviews: number;
}

export interface CostByModel {
  model_version: string;
  cost_usd: number;
  reviews: number;
}

export interface BudgetStatus {
  daily_budget_usd: number | null;
  today_cost_usd: number;
  today_percent_of_budget: number;
  circuit_breaker_threshold: number | null;
}

export interface CostSummary {
  range: string;
  range_days: number;
  total_cost_usd: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_reviews: number;
  daily: CostDailyRow[];
  by_step: CostByStep[];
  by_model: CostByModel[];
  budget: BudgetStatus;
}

// ---- Prompts -------------------------------------------------------------

export interface PromptSummary {
  hash: string;
  name: string;
  version: number;
  description: string | null;
  is_active: boolean;
  created_at: string | null;
  source: "db" | "code";
}

export interface PromptDetail extends PromptSummary {
  system_prompt: string;
  user_template: string;
}

export interface PromptListResponse {
  active: PromptSummary | null;
  prompts: PromptSummary[];
}

export interface PromptDiffEntry {
  a: string;
  b: string;
  field: string;
  unified_diff: string;
  added_lines: number;
  removed_lines: number;
}

export interface PromptDiffResponse {
  a: PromptSummary;
  b: PromptSummary;
  diffs: PromptDiffEntry[];
}

// ---- Eval ----------------------------------------------------------------

export interface EvalRunSummary {
  id: string;
  run_at: string | null;
  prompt_hash: string | null;
  model_version: string | null;
  dataset_version: string | null;
  overall_f1: number | null;
  overall_precision: number | null;
  overall_recall: number | null;
  total_prs_evaluated: number;
  avg_latency_ms: number | null;
  total_cost_usd: number | null;
  git_commit_sha: string | null;
  ci_run_url: string | null;
  source: "db" | "disk";
}

export interface EvalCategoryMetrics {
  precision: number;
  recall: number;
  f1: number;
  true_positives?: number;
  false_positives?: number;
  false_negatives?: number;
}

export interface EvalResultBlock {
  overall_precision?: number;
  overall_recall?: number;
  overall_f1?: number;
  per_category?: Record<string, EvalCategoryMetrics>;
  total_prs?: number;
}

export interface EvalCleanPRBlock {
  total_clean_prs?: number;
  clean_prs_with_any_comment?: number;
  clean_pr_fp_rate?: number;
  total_false_positive_comments?: number;
}

export interface EvalRunDetail extends EvalRunSummary {
  strict: EvalResultBlock;
  soft: EvalResultBlock;
  clean_pr: EvalCleanPRBlock;
  per_pr: Array<Record<string, unknown>>;
  notes: string | null;
}

export interface EvalRunListResponse {
  runs: EvalRunSummary[];
  sources: Record<string, boolean>;
}

export interface AblationReport {
  fixtures_total: number;
  fixtures_with_context_files: number;
  no_context: Record<string, unknown>;
  with_context: Record<string, unknown>;
  delta: Record<string, number>;
  per_pr: Array<{
    pr_id: string;
    has_context_fixture: boolean;
    no_context_comments: number;
    with_context_comments: number;
    context_chunks_supplied: number;
    retrieval_ms_with_context: number;
  }>;
  source: string;
}

// ---- Config --------------------------------------------------------------

export interface LLMConfig {
  default_model: string;
  fallback_model: string;
  mock_mode: boolean;
  has_anthropic_key: boolean;
  has_openai_key: boolean;
}

export interface CostGuardConfig {
  daily_token_budget: number;
  per_pr_token_cap: number;
  circuit_breaker_threshold: number;
  circuit_breaker_window_sec: number;
}

export interface RetrievalConfig {
  embedding_model: string;
  embedding_dim: number;
  top_k: number;
  rrf_k: number;
  per_source_top_k: number;
  recency_boost_max: number;
  recency_half_life_days: number;
  context_token_budget: number;
  diff_share: number;
  has_voyage_key: boolean;
}

/** Opt-in POST /eval/trigger — surfaced for dashboard controls. */
export interface EvalHarnessConfig {
  remote_trigger_enabled: boolean;
  trigger_force_mock: boolean;
  trigger_timeout_sec: number;
}

export interface ConfigResponse {
  version: string;
  prompt_hash: string;
  llm: LLMConfig;
  cost_guard: CostGuardConfig;
  retrieval: RetrievalConfig;
  observability: { has_langfuse_keys: boolean };
  github: {
    app_id_configured: boolean;
    webhook_secret_configured: boolean;
    private_key_path: string;
  };
  eval: EvalHarnessConfig;
  cors_origins: string[];
}

/** POST /api/v1/eval/trigger success payload */
export interface EvalTriggerResponse {
  status: string;
  exit_code: number;
  regression_gate_failed: boolean;
  forced_mock_llm: boolean;
  results_path: string;
  summary: EvalRunSummary | null;
  stderr_tail: string | null;
}

// ---- Review preview ------------------------------------------------------

export interface ReviewPreviewOutput {
  pr_title: string;
  summary: string;
  pr_quality_score: number | null;
  review_focus_areas: string[];
  comments: ReviewCommentOut[];
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  latency_ms: number;
  retrieval_ms?: number;
  prompt_hash?: string;
  model_version?: string;
}

// ---- Health --------------------------------------------------------------

export interface HealthResponse {
  status: "healthy" | "degraded" | string;
  version: string;
  checks: {
    database: string;
    llm_gateway: string;
    embeddings_index: string;
  };
}
