"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { CategoryBadge } from "@/components/badges";
import { Callout } from "@/components/callout";
import { EmptyState, ErrorPanel, LoadingBar } from "@/components/empty";
import { apiFetch } from "@/lib/api";
import { formatInt, formatPercent } from "@/lib/format";

type HealthReport = {
  hotspots: Array<{
    file_path: string;
    findings: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
    prs_affected: number;
    risk_score: number;
  }>;
  trends: Array<Record<string, number | string>>;
  patterns: Array<{
    category: string;
    signature: string;
    occurrences: number;
    prs_affected: number;
    files_affected: string[];
  }>;
  impact: {
    resolved: number;
    dismissed: number;
    resolution_rate: number;
    per_category_rates: Record<string, number>;
    most_valued_category: string | null;
  } | null;
  modules: Array<{
    module: string;
    findings: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
    health_score: number;
  }>;
  complexity: Array<{
    bucket: string;
    pr_count: number;
    avg_tokens: number;
    avg_findings: number;
  }>;
  insights: string[];
  total_prs_reviewed: number;
  total_findings: number;
};

const PERIODS = [7, 30, 90] as const;

export default function HealthPage() {
  const [days, setDays] = useState<(typeof PERIODS)[number]>(30);
  const report = useQuery<HealthReport>({
    queryKey: ["health-report", days],
    queryFn: () => apiFetch<HealthReport>(`/api/v1/health/report?days=${days}`),
  });

  const kpis = useMemo(() => {
    const d = report.data;
    if (!d) return null;
    return {
      prs: d.total_prs_reviewed,
      findings: d.total_findings,
      hotspots: d.hotspots.length,
      patterns: d.patterns.length,
    };
  }, [report.data]);

  if (report.isLoading) return <LoadingBar />;
  if (report.isError) return <ErrorPanel error={report.error} />;
  if (!report.data || !kpis) return null;

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-1">
          <h1 className="text-2xl font-semibold">Codebase Health</h1>
          <p className="text-sm text-muted">
            Organization-wide insights from historical Sentinel review data.
          </p>
        </div>
        <div className="flex gap-2 rounded border border-border bg-panel p-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setDays(p)}
              className={`rounded px-3 py-1 text-xs ${
                p === days ? "bg-panel2 text-fg" : "text-muted hover:text-fg"
              }`}
            >
              {p}d
            </button>
          ))}
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="PRs reviewed" value={formatInt(kpis.prs)} />
        <Stat label="Total findings" value={formatInt(kpis.findings)} />
        <Stat label="Hotspot files" value={formatInt(kpis.hotspots)} />
        <Stat label="Recurring patterns" value={formatInt(kpis.patterns)} />
      </section>

      <Callout variant="info" title="Key insights">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {report.data.insights.map((insight, i) => (
            <li key={i}>{insight}</li>
          ))}
        </ul>
      </Callout>

      <section className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-3 text-sm font-semibold">File hotspots</h2>
        {report.data.hotspots.length === 0 ? (
          <EmptyState
            title="No hotspot data"
            description="Run more reviews to identify high-risk files."
          />
        ) : (
          <table className="w-full text-sm">
            <thead className="text-left text-xs uppercase tracking-wide text-muted">
              <tr>
                <th className="py-1 font-medium">File</th>
                <th className="py-1 text-right font-medium">Findings</th>
                <th className="py-1 text-right font-medium">Critical</th>
                <th className="py-1 text-right font-medium">High</th>
                <th className="py-1 text-right font-medium">PRs</th>
                <th className="py-1 text-right font-medium">Risk</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {report.data.hotspots.slice(0, 12).map((row) => (
                <tr key={row.file_path}>
                  <td className="py-2 font-mono text-xs">{row.file_path}</td>
                  <td className="py-2 text-right font-mono text-xs">{formatInt(row.findings)}</td>
                  <td className="py-2 text-right font-mono text-xs text-crit">{formatInt(row.critical)}</td>
                  <td className="py-2 text-right font-mono text-xs text-bad">{formatInt(row.high)}</td>
                  <td className="py-2 text-right font-mono text-xs">{formatInt(row.prs_affected)}</td>
                  <td className="py-2 text-right font-mono text-xs">{formatInt(row.risk_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-3 text-sm font-semibold">Module health scores</h2>
        {report.data.modules.length === 0 ? (
          <EmptyState title="No module data" description="No findings yet for this window." />
        ) : (
          <div className="space-y-3">
            {report.data.modules.slice(0, 10).map((m) => (
              <div key={m.module}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="font-mono">{m.module}</span>
                  <span
                    className={
                      m.health_score >= 80
                        ? "text-ok"
                        : m.health_score >= 60
                          ? "text-warn"
                          : "text-bad"
                    }
                  >
                    {m.health_score}/100
                  </span>
                </div>
                <div className="h-2 rounded bg-panel2">
                  <div
                    className={`h-2 rounded ${
                      m.health_score >= 80
                        ? "bg-ok"
                        : m.health_score >= 60
                          ? "bg-warn"
                          : "bg-bad"
                    }`}
                    style={{ width: `${Math.max(2, m.health_score)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-3 text-sm font-semibold">Recurring patterns</h2>
        {report.data.patterns.length === 0 ? (
          <EmptyState title="No recurring patterns" description="No multi-PR patterns in this window." />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {report.data.patterns.slice(0, 8).map((p, idx) => (
              <div key={`${p.signature}-${idx}`} className="rounded border border-border bg-panel2 p-3">
                <div className="mb-1 flex items-center justify-between">
                  <CategoryBadge category={p.category} />
                  <span className="text-xs text-muted">{formatInt(p.occurrences)} occurrences</span>
                </div>
                <div className="text-sm font-medium">{p.signature}</div>
                <div className="mt-1 text-xs text-muted">
                  {formatInt(p.prs_affected)} PRs, {formatInt(p.files_affected.length)} files
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-3 text-sm font-semibold">Review impact</h2>
        {!report.data.impact ? (
          <EmptyState title="No feedback impact yet" description="Collect more feedback events for resolution metrics." />
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Resolution rate" value={formatPercent(report.data.impact.resolution_rate)} />
            <Stat label="Resolved" value={formatInt(report.data.impact.resolved)} />
            <Stat label="Dismissed" value={formatInt(report.data.impact.dismissed)} />
            <Stat
              label="Most valued"
              value={report.data.impact.most_valued_category || "—"}
            />
          </div>
        )}
      </section>
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
