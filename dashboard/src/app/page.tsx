"use client";

import Link from "next/link";
import clsx from "clsx";
import { Callout } from "@/components/callout";
import { ErrorPanel, LoadingBar } from "@/components/empty";
import { useHealth } from "@/hooks/health";
import { useReviews } from "@/hooks/reviews";
import { useFeedbackStats } from "@/hooks/feedback";
import { formatInt, formatPercent } from "@/lib/format";

const HEALTH_DOT: Record<string, string> = {
  healthy: "bg-ok",
  degraded: "bg-warn",
};

export default function HomePage() {
  const health = useHealth();
  const recent = useReviews({ page: 1, per_page: 1 });
  const feedback = useFeedbackStats({ days: 30 });

  return (
    <div className="space-y-8">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Sentinel</h1>
        <p className="text-sm text-muted">
          AI-powered code review with reproducible evaluation.
        </p>
      </header>

      <Callout variant="security" title="Operate this dashboard securely">
        <p>
          Serve the UI over HTTPS in production, restrict network access to the API,
          and enable backend <code className="text-info">API_KEY</code> plus{" "}
          <code className="text-info">NEXT_PUBLIC_API_KEY</code> only when both ends
          stay private to your team. This UI is read-oriented but can expose metrics
          about repos and spend — treat access like admin tooling.
        </p>
      </Callout>

      <HealthCard />

      <section className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <Kpi
          label="Reviews logged"
          value={
            recent.isLoading
              ? "—"
              : recent.isError
                ? "—"
                : formatInt(recent.data?.total ?? 0)
          }
          subtitle={
            recent.isError
              ? "API unreachable — is the backend running on port 8000?"
              : "all-time, /api/v1/reviews"
          }
          href="/reviews"
        />
        <Kpi
          label="Feedback agreement (30d)"
          value={
            feedback.isLoading
              ? "—"
              : feedback.isError
                ? "—"
                : formatPercent(feedback.data?.agreement_rate ?? 0)
          }
          subtitle={
            feedback.isError
              ? "API unreachable — start FastAPI or check NEXT_PUBLIC_API_URL"
              : feedback.data
                ? `${formatInt(feedback.data.total_events)} events`
                : "resolved / (resolved + dismissed)"
          }
          href="/feedback"
        />
        <Kpi
          label="LLM gateway"
          value={
            health.isLoading
              ? "—"
              : health.data?.checks.llm_gateway === "live"
                ? "Live"
                : "Mock"
          }
          subtitle={
            health.data
              ? `db: ${health.data.checks.database} · index: ${health.data.checks.embeddings_index}`
              : "health endpoint"
          }
          href="/eval"
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">
          Sections
        </h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <LinkCard
            title="Reviews"
            description="PRs Sentinel has processed, with filters and per-review telemetry."
            href="/reviews"
          />
          <LinkCard
            title="Eval"
            description="Offline F1, per-category P/R, clean-PR false positive rate."
            href="/eval"
          />
          <LinkCard
            title="Costs"
            description="Daily spend and per-step LLM cost breakdown."
            href="/costs"
          />
          <LinkCard
            title="Prompts"
            description="Active prompts and their hashes, linked to persisted reviews."
            href="/prompts"
          />
          <LinkCard
            title="Feedback"
            description="Online agreement-rate from developer reactions on real PRs."
            href="/feedback"
          />
        </div>
      </section>
    </div>
  );
}

function HealthCard() {
  const { data, isLoading, isError, error } = useHealth();

  if (isLoading) {
    return (
      <div className="rounded-lg border border-border bg-panel px-4 py-3">
        <LoadingBar />
      </div>
    );
  }

  if (isError) {
    return <ErrorPanel error={error} />;
  }

  if (!data) return null;

  const dot = HEALTH_DOT[data.status] ?? "bg-muted";
  const indexMissing =
    String(data.checks.embeddings_index).toLowerCase() === "missing";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-border bg-panel px-4 py-3 text-sm shadow-sm">
        <span className={clsx("h-2 w-2 shrink-0 rounded-full ring-2 ring-black/20", dot)} />
        <span className="font-medium capitalize">{data.status}</span>
        <span className="text-muted">v{data.version}</span>
        <span className="ml-auto flex flex-wrap items-center gap-4 font-mono text-xs text-muted">
          <span>
            db:{" "}
            <span
              className={clsx(
                data.checks.database === "ok" ? "text-ok" : "text-warn",
              )}
            >
              {data.checks.database}
            </span>
          </span>
          <span>
            llm:{" "}
            <span className="text-fg">{data.checks.llm_gateway}</span>
          </span>
          <span>
            index:{" "}
            <span className={indexMissing ? "text-warn" : "text-ok"}>
              {data.checks.embeddings_index}
            </span>
          </span>
        </span>
      </div>

      {indexMissing && (
        <Callout variant="info" title="Semantic retrieval offline">
          <p>
            The embeddings index isn&apos;t available (often missing{" "}
            <code className="text-info">pgvector</code> on Postgres). BM25-only or
            keyword paths may still run; dense hybrid retrieval stays disabled until
            the DB extension is installed.
          </p>
        </Callout>
      )}
    </div>
  );
}

function Kpi({
  label,
  value,
  subtitle,
  href,
}: {
  label: string;
  value: string;
  subtitle: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-lg border border-border bg-panel px-4 py-4 transition-colors hover:border-accent/50 hover:bg-panel2"
    >
      <div className="text-xxs uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-2 text-2xl font-semibold text-fg group-hover:text-accent">
        {value}
      </div>
      <div className="mt-1 text-xs text-muted">{subtitle}</div>
    </Link>
  );
}

function LinkCard({
  title,
  description,
  href,
}: {
  title: string;
  description: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="group rounded-lg border border-border bg-panel p-4 transition-colors hover:border-accent/50 hover:bg-panel2"
    >
      <div className="text-sm font-semibold text-fg group-hover:text-accent">
        {title}
      </div>
      <p className="mt-1 text-xs text-muted">{description}</p>
    </Link>
  );
}
