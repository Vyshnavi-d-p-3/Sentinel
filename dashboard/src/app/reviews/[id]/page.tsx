"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useReview } from "@/hooks/reviews";
import {
  CategoryBadge,
  SeverityBadge,
  StatusBadge,
} from "@/components/badges";
import { ErrorPanel, LoadingBar } from "@/components/empty";
import {
  formatInt,
  formatMs,
  formatRelativeTime,
} from "@/lib/format";
import type { ReviewCommentOut, ReviewDetail } from "@/lib/types";

export default function ReviewDetailPage() {
  const params = useParams<{ id: string }>();
  const reviewId = params?.id ?? null;
  const { data, isLoading, isError, error } = useReview(reviewId);

  if (isLoading) return <LoadingBar />;
  if (isError) return <ErrorPanel error={error} />;
  if (!data) return null;

  const r = data.review;

  return (
    <div className="space-y-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs text-muted">
            <Link href="/reviews" className="hover:text-fg">
              Reviews
            </Link>{" "}
            <span>/</span>{" "}
            <span className="font-mono text-fg">
              {r.repo_name || r.repo_id.slice(0, 8)}#{r.pr_number}
            </span>
          </div>
          <h1 className="mt-1 text-2xl font-semibold">
            {r.pr_title || <span className="text-muted">(no title)</span>}
          </h1>
          <p className="mt-1 text-sm text-muted">
            {formatRelativeTime(r.created_at)} ·{" "}
            <StatusBadge status={r.status} />
          </p>
        </div>
        {r.pr_url && (
          <a
            href={r.pr_url}
            target="_blank"
            rel="noreferrer"
            className="rounded border border-border bg-panel px-3 py-1.5 text-xs text-accent hover:bg-panel2"
          >
            Open on GitHub ↗
          </a>
        )}
      </header>

      {r.summary && (
        <section className="rounded-lg border border-border bg-panel p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
            Summary
          </h2>
          <p className="text-sm text-fg">{r.summary}</p>
          {r.review_focus_areas?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {r.review_focus_areas.map((area) => (
                <span
                  key={area}
                  className="rounded-full border border-border bg-panel2 px-2 py-0.5 text-xxs text-muted"
                >
                  {area}
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      <TelemetryGrid review={r} />

      <section>
        <h2 className="mb-3 text-sm font-semibold">
          Comments{" "}
          <span className="text-muted">({r.comments.length})</span>
        </h2>
        {r.comments.length === 0 ? (
          <p className="rounded-lg border border-border bg-panel p-6 text-center text-sm text-muted">
            No comments — Sentinel decided this PR was clean.
          </p>
        ) : (
          <ul className="space-y-3">
            {r.comments.map((c, i) => (
              <CommentCard key={i} comment={c} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function TelemetryGrid({ review }: { review: ReviewDetail }) {
  const steps = review.pipeline_step_timings || {};
  const cells: { label: string; value: string }[] = [
    { label: "Quality score", value: review.pr_quality_score?.toFixed(1) ?? "—" },
    { label: "Input tokens", value: formatInt(review.input_tokens) },
    { label: "Output tokens", value: formatInt(review.output_tokens) },
    { label: "Total tokens", value: formatInt(review.total_tokens) },
    { label: "Pipeline latency", value: formatMs(review.latency_ms) },
    { label: "Retrieval latency", value: formatMs(review.retrieval_ms) },
  ];

  return (
    <section className="grid grid-cols-2 gap-3 md:grid-cols-6">
      {cells.map((cell) => (
        <div
          key={cell.label}
          className="rounded-lg border border-border bg-panel px-3 py-2"
        >
          <div className="text-xxs uppercase tracking-wide text-muted">
            {cell.label}
          </div>
          <div className="mt-1 font-mono text-sm text-fg">{cell.value}</div>
        </div>
      ))}
      {Object.entries(steps).length > 0 && (
        <div className="col-span-full rounded-lg border border-border bg-panel px-3 py-2">
          <div className="text-xxs uppercase tracking-wide text-muted">
            Per-step timings
          </div>
          <div className="mt-1 flex flex-wrap gap-3 text-xs">
            {Object.entries(steps).map(([step, ms]) => (
              <span
                key={step}
                className="font-mono text-muted"
              >
                <span className="text-fg">{step}</span>: {formatMs(Number(ms))}
              </span>
            ))}
          </div>
        </div>
      )}
      <div className="col-span-full grid grid-cols-2 gap-3 md:grid-cols-3">
        <MetaCell label="Diff hash" value={review.diff_hash?.slice(0, 16) || "—"} />
        <MetaCell label="Prompt hash" value={review.prompt_hash?.slice(0, 16) || "—"} />
        <MetaCell label="Model" value={review.model_version || "—"} />
      </div>
    </section>
  );
}

function MetaCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-panel px-3 py-2">
      <div className="text-xxs uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 truncate font-mono text-xs text-fg">{value}</div>
    </div>
  );
}

function CommentCard({ comment }: { comment: ReviewCommentOut }) {
  return (
    <li className="rounded-lg border border-border bg-panel p-4">
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
        <SeverityBadge severity={comment.severity} />
        <CategoryBadge category={comment.category} />
        <span className="font-mono">
          {comment.file_path}:{comment.line_number}
        </span>
        {typeof comment.confidence === "number" && (
          <span className="font-mono">
            conf {(comment.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
      <p className="mt-2 text-sm text-fg">{comment.description}</p>
      {comment.suggestion && (
        <pre className="mt-2 overflow-x-auto rounded border border-border bg-panel2 p-2 text-xs text-muted">
          {comment.suggestion}
        </pre>
      )}
      {comment.related_files && comment.related_files.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5 text-xxs text-muted">
          <span>Related:</span>
          {comment.related_files.map((path) => (
            <span key={path} className="font-mono text-fg">
              {path}
            </span>
          ))}
        </div>
      )}
    </li>
  );
}
