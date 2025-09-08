"use client";

import { useState } from "react";
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
import { useCostSummary } from "@/hooks/costs";
import { EmptyState, ErrorPanel, LoadingBar } from "@/components/empty";
import { formatInt, formatPercent } from "@/lib/format";

const RANGES = ["1d", "7d", "14d", "30d", "90d"] as const;

function formatUsd(value: number | null | undefined, digits = 2): string {
  if (value == null || !isFinite(value)) return "—";
  if (value === 0) return "$0.00";
  if (value < 0.01) return "<$0.01";
  return `$${value.toFixed(digits)}`;
}

export default function CostsPage() {
  const [range, setRange] = useState<(typeof RANGES)[number]>("7d");
  const { data, isLoading, isError, error } = useCostSummary({ range });

  if (isLoading) return <LoadingBar />;
  if (isError) return <ErrorPanel error={error} />;
  if (!data) return null;

  const noData = data.total_reviews === 0 && data.total_cost_usd === 0;
  const budgetPct = data.budget.daily_budget_usd
    ? data.budget.today_percent_of_budget
    : 0;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">Costs</h1>
          <p className="text-sm text-muted">
            LLM spend, token usage, and budget burn across the selected window.
          </p>
        </div>
        <div className="flex gap-1 rounded-md border border-border bg-panel p-1">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`rounded px-3 py-1 text-xs font-medium ${
                r === range
                  ? "bg-accent text-bg"
                  : "text-muted hover:text-fg"
              }`}
            >
              {r}
            </button>
          ))}
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={`Total (${data.range})`} value={formatUsd(data.total_cost_usd, 4)} />
        <Stat label="Reviews" value={formatInt(data.total_reviews)} />
        <Stat
          label="Tokens in / out"
          value={`${formatInt(data.total_input_tokens)} / ${formatInt(data.total_output_tokens)}`}
        />
        <BudgetTile
          todayUsd={data.budget.today_cost_usd}
          dailyBudgetUsd={data.budget.daily_budget_usd}
          pct={budgetPct}
        />
      </section>

      {noData ? (
        <EmptyState
          title="No cost activity yet"
          description="Run a review to populate the cost ledger. Every step (triage, deep review, cross-reference, synthesis) records its own row."
        />
      ) : (
        <>
          <section className="rounded-lg border border-border bg-panel p-4">
            <h2 className="mb-4 text-sm font-semibold">
              Daily spend — last {data.range_days} days
            </h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={data.daily}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#242a33" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#8891a0", fontSize: 11 }}
                    stroke="#242a33"
                  />
                  <YAxis
                    tick={{ fill: "#8891a0", fontSize: 11 }}
                    stroke="#242a33"
                    tickFormatter={(v) => `$${v.toFixed?.(2) ?? v}`}
                  />
                  <Tooltip
                    cursor={{ fill: "#171b22" }}
                    contentStyle={{
                      background: "#12151a",
                      border: "1px solid #242a33",
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                    formatter={(value: number, name: string) =>
                      name === "cost_usd" ? [formatUsd(value, 4), "cost"] : [value, name]
                    }
                  />
                  <Bar dataKey="cost_usd" fill="#6aa7ff" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-panel p-4">
            <h2 className="mb-4 text-sm font-semibold">Token volume per day</h2>
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.daily}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#242a33" />
                  <XAxis dataKey="date" tick={{ fill: "#8891a0", fontSize: 11 }} stroke="#242a33" />
                  <YAxis tick={{ fill: "#8891a0", fontSize: 11 }} stroke="#242a33" />
                  <Tooltip
                    cursor={{ fill: "#171b22" }}
                    contentStyle={{
                      background: "#12151a",
                      border: "1px solid #242a33",
                      borderRadius: 6,
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="input_tokens" stroke="#4ade80" dot={false} />
                  <Line type="monotone" dataKey="output_tokens" stroke="#f59e0b" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-lg border border-border bg-panel p-4">
              <h2 className="mb-3 text-sm font-semibold">By pipeline step</h2>
              {data.by_step.length === 0 ? (
                <p className="text-sm text-muted">No step-level cost ledger rows yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="text-left text-xs uppercase tracking-wide text-muted">
                    <tr>
                      <th className="py-1 font-medium">Step</th>
                      <th className="py-1 text-right font-medium">Cost</th>
                      <th className="py-1 text-right font-medium">In</th>
                      <th className="py-1 text-right font-medium">Out</th>
                      <th className="py-1 text-right font-medium">Reviews</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data.by_step.map((row) => (
                      <tr key={row.step}>
                        <td className="py-2 font-mono text-xs text-fg">{row.step}</td>
                        <td className="py-2 text-right font-mono text-xs text-fg">
                          {formatUsd(row.cost_usd, 4)}
                        </td>
                        <td className="py-2 text-right font-mono text-xs text-muted">
                          {formatInt(row.input_tokens)}
                        </td>
                        <td className="py-2 text-right font-mono text-xs text-muted">
                          {formatInt(row.output_tokens)}
                        </td>
                        <td className="py-2 text-right font-mono text-xs text-muted">
                          {formatInt(row.reviews)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="rounded-lg border border-border bg-panel p-4">
              <h2 className="mb-3 text-sm font-semibold">By model</h2>
              {data.by_model.length === 0 ? (
                <p className="text-sm text-muted">No model-level data yet.</p>
              ) : (
                <table className="w-full text-sm">
                  <thead className="text-left text-xs uppercase tracking-wide text-muted">
                    <tr>
                      <th className="py-1 font-medium">Model</th>
                      <th className="py-1 text-right font-medium">Cost</th>
                      <th className="py-1 text-right font-medium">Share</th>
                      <th className="py-1 text-right font-medium">Reviews</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {data.by_model.map((row) => {
                      const share =
                        data.total_cost_usd > 0
                          ? row.cost_usd / data.total_cost_usd
                          : 0;
                      return (
                        <tr key={row.model_version}>
                          <td className="py-2 font-mono text-xs text-fg">
                            {row.model_version}
                          </td>
                          <td className="py-2 text-right font-mono text-xs text-fg">
                            {formatUsd(row.cost_usd, 4)}
                          </td>
                          <td className="py-2 text-right font-mono text-xs text-muted">
                            {formatPercent(share)}
                          </td>
                          <td className="py-2 text-right font-mono text-xs text-muted">
                            {formatInt(row.reviews)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-panel px-3 py-3">
      <div className="text-xxs uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 font-mono text-xl text-fg">{value}</div>
    </div>
  );
}

function BudgetTile({
  todayUsd,
  dailyBudgetUsd,
  pct,
}: {
  todayUsd: number;
  dailyBudgetUsd: number | null;
  pct: number;
}) {
  const clamped = Math.min(pct, 1);
  const over = pct > 1;
  const tone = over ? "bg-bad" : pct > 0.8 ? "bg-warn" : "bg-ok";
  return (
    <div className="rounded-lg border border-border bg-panel px-3 py-3">
      <div className="text-xxs uppercase tracking-wide text-muted">
        Today vs. daily budget
      </div>
      <div className="mt-1 font-mono text-xl text-fg">
        {formatUsd(todayUsd, 4)}
        {dailyBudgetUsd ? (
          <span className="ml-1 text-xs text-muted">
            / {formatUsd(dailyBudgetUsd, 2)}
          </span>
        ) : null}
      </div>
      <div className="mt-2 h-1.5 w-full overflow-hidden rounded bg-panel2">
        <div
          className={`h-full ${tone}`}
          style={{ width: `${clamped * 100}%` }}
        />
      </div>
      <div className="mt-1 text-xxs text-muted">
        {dailyBudgetUsd ? `${formatPercent(pct)} used` : "no budget configured"}
        {over && dailyBudgetUsd ? " — over" : ""}
      </div>
    </div>
  );
}
