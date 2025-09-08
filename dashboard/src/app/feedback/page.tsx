"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useFeedbackStats, useRecentFeedback } from "@/hooks/feedback";
import { EmptyState, ErrorPanel, LoadingBar } from "@/components/empty";
import { CategoryBadge } from "@/components/badges";
import { formatInt, formatPercent, formatRelativeTime } from "@/lib/format";

export default function FeedbackPage() {
  const stats = useFeedbackStats({ days: 30 });
  const recent = useRecentFeedback({ limit: 25 });

  if (stats.isLoading) return <LoadingBar />;
  if (stats.isError) return <ErrorPanel error={stats.error} />;
  if (!stats.data) return null;

  const d = stats.data;
  const noData = d.total_events === 0;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Feedback</h1>
        <p className="text-sm text-muted">
          Developer reactions to Sentinel&apos;s comments. Agreement rate is{" "}
          <code className="rounded bg-panel2 px-1 text-accent">
            resolved / (resolved + dismissed)
          </code>
          .
        </p>
      </header>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Stat label="Agreement" value={formatPercent(d.agreement_rate)} />
        <Stat label="Events" value={formatInt(d.total_events)} />
        <Stat label="Resolved" value={formatInt(d.resolved)} tone="ok" />
        <Stat label="Dismissed" value={formatInt(d.dismissed)} tone="bad" />
        <Stat label="Replied" value={formatInt(d.replied)} />
      </section>

      {noData ? (
        <EmptyState
          title="No feedback events yet"
          description="Once developers react to Sentinel's PR comments — resolve, dismiss, or reply — data will appear here."
        />
      ) : (
        <>
          <section className="rounded-lg border border-border bg-panel p-4">
            <h2 className="mb-4 text-sm font-semibold">
              Agreement rate — last {d.window_days} days
            </h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={d.by_day}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#242a33" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: "#8891a0", fontSize: 11 }}
                    stroke="#242a33"
                  />
                  <YAxis
                    tick={{ fill: "#8891a0", fontSize: 11 }}
                    stroke="#242a33"
                    allowDecimals={false}
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
                  <Bar dataKey="resolved" stackId="a" fill="#4ade80" />
                  <Bar dataKey="dismissed" stackId="a" fill="#f87171" />
                  <Bar dataKey="replied" stackId="a" fill="#6aa7ff" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="rounded-lg border border-border bg-panel p-4">
            <h2 className="mb-3 text-sm font-semibold">Category breakdown</h2>
            {d.by_category.length === 0 ? (
              <p className="text-sm text-muted">
                No per-category data — events lack category hints.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase tracking-wide text-muted">
                  <tr>
                    <th className="py-1 font-medium">Category</th>
                    <th className="py-1 text-right font-medium">Agreement</th>
                    <th className="py-1 text-right font-medium">Resolved</th>
                    <th className="py-1 text-right font-medium">Dismissed</th>
                    <th className="py-1 text-right font-medium">Replied</th>
                    <th className="py-1 text-right font-medium">Total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {d.by_category.map((row) => (
                    <tr key={row.category}>
                      <td className="py-2">
                        <CategoryBadge category={row.category} />
                      </td>
                      <td className="py-2 text-right font-mono text-xs text-fg">
                        {formatPercent(row.agreement_rate)}
                      </td>
                      <td className="py-2 text-right font-mono text-xs text-ok">
                        {formatInt(row.resolved)}
                      </td>
                      <td className="py-2 text-right font-mono text-xs text-bad">
                        {formatInt(row.dismissed)}
                      </td>
                      <td className="py-2 text-right font-mono text-xs text-muted">
                        {formatInt(row.replied)}
                      </td>
                      <td className="py-2 text-right font-mono text-xs text-muted">
                        {formatInt(row.total)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}

      <section className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-3 text-sm font-semibold">Recent events</h2>
        {recent.isLoading ? (
          <LoadingBar />
        ) : !recent.data?.length ? (
          <p className="text-sm text-muted">No recent events.</p>
        ) : (
          <ul className="divide-y divide-border text-sm">
            {recent.data.map((ev) => (
              <li key={ev.id} className="flex items-center gap-3 py-2">
                <span className="w-20 font-mono text-xs text-muted">
                  {ev.action}
                </span>
                {ev.category && <CategoryBadge category={ev.category} />}
                {ev.github_user && (
                  <span className="text-xs text-muted">
                    by <span className="text-fg">{ev.github_user}</span>
                  </span>
                )}
                {ev.reply_body && (
                  <span className="truncate text-xs text-fg" title={ev.reply_body}>
                    “{ev.reply_body}”
                  </span>
                )}
                <span className="ml-auto text-xs text-muted">
                  {formatRelativeTime(ev.created_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
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
