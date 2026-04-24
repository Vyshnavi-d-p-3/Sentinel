"use client";

import { useConfig } from "@/hooks/config";
import { usePatchRepoSettings, useReposList } from "@/hooks/repos";
import { Callout } from "@/components/callout";
import { ErrorPanel, LoadingBar } from "@/components/empty";
import { formatInt } from "@/lib/format";

export default function SettingsPage() {
  const { data, isLoading, isError, error } = useConfig();

  if (isLoading) return <LoadingBar />;
  if (isError) return <ErrorPanel error={error} />;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-sm text-muted">
          Effective runtime configuration loaded from environment variables. Secrets
          are never surfaced — only whether they&apos;re configured.
        </p>
      </header>

      <Callout variant="warning" title="Browser-exposed configuration">
        <p>
          Values prefixed with{" "}
          <code className="text-warn">NEXT_PUBLIC_</code> ship to every visitor&apos;s
          browser bundle. Never put secrets there — use server-side env or an API proxy.
          For dashboard auth, prefer short-lived tokens over long-lived keys when possible.
        </p>
      </Callout>

      <RepoInstallationsBlock />

      <section className="grid gap-4 lg:grid-cols-2">
        <Card title="Build">
          <Row label="Sentinel version">
            <span className="font-mono">{data.version}</span>
          </Row>
          <Row label="Prompt hash">
            <span className="font-mono text-xs">{data.prompt_hash}</span>
          </Row>
        </Card>

        <Card title="LLM gateway">
          <Row label="Mode">
            <Badge tone={data.llm.mock_mode ? "warn" : "ok"}>
              {data.llm.mock_mode ? "mock" : "live"}
            </Badge>
          </Row>
          <Row label="Default model">
            <span className="font-mono text-xs">{data.llm.default_model}</span>
          </Row>
          <Row label="Fallback model">
            <span className="font-mono text-xs">{data.llm.fallback_model}</span>
          </Row>
          <Row label="Anthropic key">
            <ConfiguredBadge value={data.llm.has_anthropic_key} />
          </Row>
          <Row label="OpenAI key">
            <ConfiguredBadge value={data.llm.has_openai_key} />
          </Row>
        </Card>

        <Card title="Cost guard">
          <Row label="Daily token budget">
            <span className="font-mono">{formatInt(data.cost_guard.daily_token_budget)}</span>
          </Row>
          <Row label="Per-PR token cap">
            <span className="font-mono">{formatInt(data.cost_guard.per_pr_token_cap)}</span>
          </Row>
          <Row label="Circuit breaker threshold">
            <span className="font-mono">{data.cost_guard.circuit_breaker_threshold}</span>
          </Row>
          <Row label="Circuit breaker window">
            <span className="font-mono">{data.cost_guard.circuit_breaker_window_sec}s</span>
          </Row>
        </Card>

        <Card title="Retrieval">
          <Row label="Embedding model">
            <span className="font-mono text-xs">{data.retrieval.embedding_model}</span>
          </Row>
          <Row label="Dimension">
            <span className="font-mono">{data.retrieval.embedding_dim}</span>
          </Row>
          <Row label="Top K">
            <span className="font-mono">{data.retrieval.top_k}</span>
          </Row>
          <Row label="RRF k">
            <span className="font-mono">{data.retrieval.rrf_k}</span>
          </Row>
          <Row label="Per-source top K">
            <span className="font-mono">{data.retrieval.per_source_top_k}</span>
          </Row>
          <Row label="Recency boost (max)">
            <span className="font-mono">
              {(data.retrieval.recency_boost_max * 100).toFixed(0)}%
            </span>
          </Row>
          <Row label="Recency half-life">
            <span className="font-mono">{data.retrieval.recency_half_life_days}d</span>
          </Row>
          <Row label="Context token budget">
            <span className="font-mono">
              {formatInt(data.retrieval.context_token_budget)}
            </span>
          </Row>
          <Row label="Diff share">
            <span className="font-mono">
              {(data.retrieval.diff_share * 100).toFixed(0)}%
            </span>
          </Row>
          <Row label="VoyageAI key">
            <ConfiguredBadge value={data.retrieval.has_voyage_key} />
          </Row>
        </Card>

        <Card title="GitHub App">
          <Row label="App ID">
            <ConfiguredBadge value={data.github.app_id_configured} />
          </Row>
          <Row label="Webhook secret">
            <ConfiguredBadge value={data.github.webhook_secret_configured} />
          </Row>
          <Row label="Private key path">
            <span className="font-mono text-xs">{data.github.private_key_path}</span>
          </Row>
        </Card>

        <Card title="Observability">
          <Row label="Langfuse">
            <ConfiguredBadge value={data.observability.has_langfuse_keys} />
          </Row>
        </Card>

        <Card title="Eval harness">
          <Row label="Remote trigger (POST /eval/trigger)">
            <ConfiguredBadge value={data.eval.remote_trigger_enabled} />
          </Row>
          <Row label="Force mock LLM in subprocess">
            <Badge tone={data.eval.trigger_force_mock ? "warn" : "ok"}>
              {data.eval.trigger_force_mock ? "yes" : "no"}
            </Badge>
          </Row>
          <Row label="Subprocess timeout">
            <span className="font-mono">{Math.round(data.eval.trigger_timeout_sec)}s</span>
          </Row>
        </Card>

        <Card title="CORS">
          <div className="space-y-1">
            {data.cors_origins.map((origin) => (
              <div key={origin} className="font-mono text-xs text-muted">
                {origin}
              </div>
            ))}
          </div>
        </Card>
      </section>
    </div>
  );
}

function RepoInstallationsBlock() {
  const { data, isLoading, isError, error } = useReposList(1, 50);
  const patch = usePatchRepoSettings();

  if (isLoading) {
    return (
      <p className="text-sm text-muted" role="status">
        Loading registered repositories…
      </p>
    );
  }
  if (isError) return <ErrorPanel error={error} />;

  if (!data?.repos.length) {
    return (
      <Callout variant="info" title="No repository installations">
        <p className="text-sm">
          When the GitHub App is installed, each repository appears here. You can toggle
          per-repo <strong>auto-review</strong> and adjust token budgets (via API) without
          changing global environment defaults.
        </p>
      </Callout>
    );
  }

  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      <h2 className="mb-3 text-sm font-semibold">Repository installations</h2>
      <div className="space-y-3">
        {data.repos.map((repo) => (
          <div
            key={repo.id}
            className="flex flex-col gap-2 border-b border-border/40 pb-3 last:border-b-0 sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <div className="font-mono text-sm text-fg">{repo.full_name}</div>
              <div className="text-xxs text-muted">
                Daily budget {formatInt(repo.daily_token_budget)} — per-PR cap{" "}
                {formatInt(repo.per_pr_token_cap)} — default branch {repo.default_branch}
              </div>
            </div>
            <button
              type="button"
              className="shrink-0 self-start rounded-md border border-border bg-panel2 px-3 py-1.5 text-sm text-fg hover:border-accent/50 disabled:opacity-50"
              disabled={patch.isPending}
              onClick={() =>
                patch.mutate({ id: repo.id, body: { auto_review: !repo.auto_review } })
              }
            >
              Auto-review: {repo.auto_review ? "on" : "off"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-panel p-4">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/40 pb-1 last:border-b-0 last:pb-0">
      <span className="text-xs text-muted">{label}</span>
      <span className="text-sm text-fg">{children}</span>
    </div>
  );
}

function Badge({
  tone,
  children,
}: {
  tone: "ok" | "warn" | "bad";
  children: React.ReactNode;
}) {
  const color =
    tone === "ok"
      ? "bg-ok/20 text-ok"
      : tone === "warn"
        ? "bg-warn/20 text-warn"
        : "bg-bad/20 text-bad";
  return (
    <span className={`rounded px-2 py-0.5 text-xxs font-medium ${color}`}>
      {children}
    </span>
  );
}

function ConfiguredBadge({ value }: { value: boolean }) {
  return (
    <Badge tone={value ? "ok" : "warn"}>{value ? "configured" : "not set"}</Badge>
  );
}
