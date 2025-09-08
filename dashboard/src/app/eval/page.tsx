"use client";

import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useAblation, useEvalRuns, useLatestEvalRun } from "@/hooks/eval";
import { EvalTriggerPanel } from "@/components/eval-trigger";
import { EmptyState, ErrorPanel, LoadingBar } from "@/components/empty";
import { formatInt, formatPercent, formatRelativeTime } from "@/lib/format";
import type { EvalCategoryMetrics, EvalRunSummary } from "@/lib/types";

const CATEGORY_ORDER = ["security", "bug", "performance", "perf", "style", "suggestion"];
const CATEGORY_COLORS: Record<string, string> = {
  security: "#f87171",
  bug: "#f59e0b",
  performance: "#6aa7ff",
  perf: "#6aa7ff",
  style: "#a78bfa",
  suggestion: "#4ade80",
};

function formatF1(v: number | null | undefined): string {
  if (v == null || !isFinite(v)) return "—";
  return v.toFixed(3);
}

function trendDataFromRuns(runs: EvalRunSummary[]) {
  // Reverse to chronological order for the chart.
  return [...runs]
    .filter((r) => r.run_at)
    .sort((a, b) => new Date(a.run_at ?? 0).getTime() - new Date(b.run_at ?? 0).getTime())
    .map((r) => ({
      date: (r.run_at ?? "").slice(0, 10),
      overall_f1: r.overall_f1 ?? 0,
      commit: r.git_commit_sha?.slice(0, 7) ?? "",
    }));
}

export default function EvalPage() {
  const runs = useEvalRuns();
  const latest = useLatestEvalRun();
  const ablation = useAblation();
  const [mode, setMode] = useState<"strict" | "soft">("strict");

  const hasLatest = !latest.isError && !!latest.data;
  const hasHistory = !!runs.data?.runs.length;

  const block = hasLatest
    ? mode === "strict"
      ? latest.data!.strict
      : latest.data!.soft
    : null;

  const catRows = useMemo(() => {
    const perCategory = (block?.per_category ?? {}) as Record<
      string,
      EvalCategoryMetrics
    >;
    return CATEGORY_ORDER.filter((c) => c in perCategory).map((c) => ({
      category: c,
      ...perCategory[c],
    }));
  }, [block]);

  const trendData = useMemo(
    () => (runs.data ? trendDataFromRuns(runs.data.runs) : []),
    [runs.data],
  );

  if (runs.isLoading && latest.isLoading) return <LoadingBar />;
  if (runs.isError)
    return <ErrorPanel error={runs.error} />;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Eval</h1>
        <p className="text-sm text-muted">
          Per-category precision, recall, and F1 against the hand-labeled fixtures.
          Strict matching requires line-level alignment; soft matching only checks file +
          category. Clean-PR FP rate measures noise on bug-free PRs.
        </p>
      </header>

      <EvalTriggerPanel />

      {!hasLatest ? (
        <EmptyState
          title="No eval runs yet"
          description="Run the harness locally or wait for the CI workflow: `python eval/scripts/eval_runner.py --output eval/results.json`."
        />
      ) : (
        <>
          <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
            <Stat
              label={`Overall ${mode} F1`}
              value={formatF1(block?.overall_f1)}
              tone="ok"
            />
            <Stat
              label={`${mode} precision`}
              value={formatF1(block?.overall_precision)}
            />
            <Stat
              label={`${mode} recall`}
              value={formatF1(block?.overall_recall)}
            />
            <Stat
              label="PRs evaluated"
              value={formatInt(latest.data?.total_prs_evaluated ?? 0)}
            />
            <Stat
              label="Clean-PR FP rate"
              value={formatPercent(
                latest.data?.clean_pr?.clean_pr_fp_rate ?? 0,
              )}
              tone={
                (latest.data?.clean_pr?.clean_pr_fp_rate ?? 0) > 0.1
                  ? "bad"
                  : "ok"
              }
            />
          </section>

          <section className="rounded-lg border border-border bg-panel p-4">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Per-category {mode} F1</h2>
              <div className="flex gap-1 rounded-md border border-border bg-panel2 p-1">
                {(["strict", "soft"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`rounded px-2 py-1 text-xs font-medium ${
                      m === mode ? "bg-accent text-bg" : "text-muted hover:text-fg"
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            </div>
            {catRows.length === 0 ? (
              <p className="text-sm text-muted">No per-category data in this run.</p>
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={catRows}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#242a33" />
                    <XAxis
                      dataKey="category"
                      tick={{ fill: "#8891a0", fontSize: 11 }}
                      stroke="#242a33"
                    />
                    <YAxis
                      domain={[0, 1]}
                      tick={{ fill: "#8891a0", fontSize: 11 }}
                      stroke="#242a33"
                      tickFormatter={(v) => v.toFixed(1)}
                    />
                    <Tooltip
                      cursor={{ fill: "#171b22" }}
                      contentStyle={{
                        background: "#12151a",
                        border: "1px solid #242a33",
                        borderRadius: 6,
                        fontSize: 12,
                      }}
                      formatter={(v: number) => v.toFixed(3)}
                    />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Bar dataKey="precision" fill="#6aa7ff" />
                    <Bar dataKey="recall" fill="#f59e0b" />
                    <Bar dataKey="f1" fill="#4ade80" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {catRows.length > 0 && (
              <table className="mt-4 w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th className="py-1 font-medium">Category</th>
                    <th className="py-1 text-right font-medium">Precision</th>
                    <th className="py-1 text-right font-medium">Recall</th>
                    <th className="py-1 text-right font-medium">F1</th>
                    <th className="py-1 text-right font-medium">TP / FP / FN</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {catRows.map((row) => (
                    <tr key={row.category}>
                      <td className="py-2">
                        <span
                          className="rounded px-2 py-0.5 text-xxs font-medium"
                          style={{
                            backgroundColor: `${CATEGORY_COLORS[row.category] ?? "#6aa7ff"}26`,
                            color: CATEGORY_COLORS[row.category] ?? "#6aa7ff",
                          }}
                        >
                          {row.category}
                        </span>
                      </td>
                      <td className="py-2 text-right font-mono text-xs text-fg">
                        {formatF1(row.precision)}
                      </td>
                      <td className="py-2 text-right font-mono text-xs text-fg">
                        {formatF1(row.recall)}
                      </td>
                      <td className="py-2 text-right font-mono text-xs text-ok">
                        {formatF1(row.f1)}
                      </td>
                      <td className="py-2 text-right font-mono text-xxs text-muted">
                        {row.true_positives ?? 0} / {row.false_positives ?? 0} /{" "}
                        {row.false_negatives ?? 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          {hasHistory && trendData.length > 1 && (
            <section className="rounded-lg border border-border bg-panel p-4">
              <h2 className="mb-4 text-sm font-semibold">Overall F1 over time</h2>
              <div className="h-56">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#242a33" />
                    <XAxis
                      dataKey="date"
                      tick={{ fill: "#8891a0", fontSize: 11 }}
                      stroke="#242a33"
                    />
                    <YAxis
                      domain={[0, 1]}
                      tick={{ fill: "#8891a0", fontSize: 11 }}
                      stroke="#242a33"
                      tickFormatter={(v) => v.toFixed(2)}
                    />
                    <Tooltip
                      cursor={{ fill: "#171b22" }}
                      contentStyle={{
                        background: "#12151a",
                        border: "1px solid #242a33",
                        borderRadius: 6,
                        fontSize: 12,
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="overall_f1"
                      stroke="#4ade80"
                      strokeWidth={2}
                      dot={{ r: 3 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </section>
          )}
        </>
      )}

      <AblationSection />

      <section className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-3 text-sm font-semibold">Run history</h2>
        {!hasHistory ? (
          <p className="text-sm text-muted">No runs indexed yet.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="py-1 font-medium">When</th>
                <th className="py-1 font-medium">Prompt</th>
                <th className="py-1 font-medium">Model</th>
                <th className="py-1 text-right font-medium">PRs</th>
                <th className="py-1 text-right font-medium">F1</th>
                <th className="py-1 text-right font-medium">Cost</th>
                <th className="py-1 font-medium">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {runs.data!.runs.map((r) => (
                <tr key={r.id}>
                  <td className="py-2 text-xs text-muted">
                    {r.run_at ? formatRelativeTime(r.run_at) : "—"}
                  </td>
                  <td className="py-2 font-mono text-xs text-fg">
                    {r.prompt_hash ? r.prompt_hash.slice(0, 7) : "—"}
                  </td>
                  <td className="py-2 font-mono text-xs text-muted">
                    {r.model_version ?? "—"}
                  </td>
                  <td className="py-2 text-right font-mono text-xs text-muted">
                    {formatInt(r.total_prs_evaluated)}
                  </td>
                  <td className="py-2 text-right font-mono text-xs text-ok">
                    {formatF1(r.overall_f1)}
                  </td>
                  <td className="py-2 text-right font-mono text-xs text-muted">
                    {r.total_cost_usd != null
                      ? `$${r.total_cost_usd.toFixed(3)}`
                      : "—"}
                  </td>
                  <td className="py-2 text-xxs text-muted">{r.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}

function AblationSection() {
  const ablation = useAblation();

  if (ablation.isLoading) {
    return (
      <section className="rounded-lg border border-border bg-panel p-4">
        <LoadingBar />
      </section>
    );
  }

  if (ablation.isError || !ablation.data) {
    return (
      <section className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-2 text-sm font-semibold">Retrieval ablation</h2>
        <p className="text-sm text-muted">
          No ablation artifact. Run{" "}
          <code className="rounded bg-panel2 px-1 text-accent">
            python eval/scripts/ablation.py
          </code>{" "}
          to generate one.
        </p>
      </section>
    );
  }

  const data = ablation.data;
  const deltaKeys = Object.keys(data.delta);
  const overallStrictDelta = data.delta["overall_strict_f1"] ?? 0;
  const overallSoftDelta = data.delta["overall_soft_f1"] ?? 0;

  return (
    <section className="rounded-lg border border-border bg-panel p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Retrieval ablation</h2>
        <span className="text-xxs text-muted">
          {data.fixtures_with_context_files} / {data.fixtures_total} fixtures have
          context
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <DeltaTile
          label="Overall strict F1 lift"
          value={overallStrictDelta}
          fmt={(v) => (v >= 0 ? `+${v.toFixed(3)}` : v.toFixed(3))}
        />
        <DeltaTile
          label="Overall soft F1 lift"
          value={overallSoftDelta}
          fmt={(v) => (v >= 0 ? `+${v.toFixed(3)}` : v.toFixed(3))}
        />
        <Stat
          label="With-context comments"
          value={formatInt(
            data.per_pr.reduce((s, r) => s + (r.with_context_comments ?? 0), 0),
          )}
        />
        <Stat
          label="Without-context comments"
          value={formatInt(
            data.per_pr.reduce((s, r) => s + (r.no_context_comments ?? 0), 0),
          )}
        />
      </div>

      {deltaKeys.length > 0 && (
        <div className="mt-4 h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={deltaKeys
                .filter((k) => k.endsWith("_strict_f1") && k !== "overall_strict_f1")
                .map((k) => ({
                  category: k.replace("_strict_f1", ""),
                  delta: data.delta[k] ?? 0,
                }))}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#242a33" />
              <XAxis dataKey="category" tick={{ fill: "#8891a0", fontSize: 11 }} stroke="#242a33" />
              <YAxis tick={{ fill: "#8891a0", fontSize: 11 }} stroke="#242a33" />
              <Tooltip
                cursor={{ fill: "#171b22" }}
                contentStyle={{
                  background: "#12151a",
                  border: "1px solid #242a33",
                  borderRadius: 6,
                  fontSize: 12,
                }}
                formatter={(v: number) => v.toFixed(3)}
              />
              <Bar dataKey="delta" fill="#4ade80" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {data.per_pr.length > 0 && (
        <table className="mt-4 w-full text-sm">
          <thead className="text-left text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="py-1 font-medium">Fixture</th>
              <th className="py-1 text-right font-medium">Has context</th>
              <th className="py-1 text-right font-medium">No-ctx comments</th>
              <th className="py-1 text-right font-medium">With-ctx comments</th>
              <th className="py-1 text-right font-medium">Chunks</th>
              <th className="py-1 text-right font-medium">Retrieval ms</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.per_pr.map((r) => (
              <tr key={r.pr_id}>
                <td className="py-2 font-mono text-xs text-fg">{r.pr_id}</td>
                <td className="py-2 text-right text-xs text-muted">
                  {r.has_context_fixture ? "yes" : "no"}
                </td>
                <td className="py-2 text-right font-mono text-xs text-muted">
                  {formatInt(r.no_context_comments)}
                </td>
                <td className="py-2 text-right font-mono text-xs text-fg">
                  {formatInt(r.with_context_comments)}
                </td>
                <td className="py-2 text-right font-mono text-xs text-muted">
                  {formatInt(r.context_chunks_supplied)}
                </td>
                <td className="py-2 text-right font-mono text-xs text-muted">
                  {formatInt(r.retrieval_ms_with_context)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "ok" | "bad";
}) {
  const valueTone =
    tone === "ok" ? "text-ok" : tone === "bad" ? "text-bad" : "text-fg";
  return (
    <div className="rounded-lg border border-border bg-panel px-3 py-3">
      <div className="text-xxs uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-1 font-mono text-xl ${valueTone}`}>{value}</div>
    </div>
  );
}

function DeltaTile({
  label,
  value,
  fmt,
}: {
  label: string;
  value: number;
  fmt: (v: number) => string;
}) {
  const tone = value > 0 ? "text-ok" : value < 0 ? "text-bad" : "text-muted";
  return (
    <div className="rounded-lg border border-border bg-panel px-3 py-3">
      <div className="text-xxs uppercase tracking-wide text-muted">{label}</div>
      <div className={`mt-1 font-mono text-xl ${tone}`}>{fmt(value)}</div>
    </div>
  );
}
