"use client";

import { useState } from "react";
import { useReviewPreview } from "@/hooks/config";
import { CategoryBadge, SeverityBadge } from "@/components/badges";
import { Callout } from "@/components/callout";
import { EmptyState, ErrorPanel } from "@/components/empty";
import { formatInt, formatMs } from "@/lib/format";
import type { ReviewCommentOut } from "@/lib/types";

const SAMPLE_DIFF = `diff --git a/auth/session.py b/auth/session.py
--- a/auth/session.py
+++ b/auth/session.py
@@ -12,7 +12,7 @@ from datetime import timedelta

-SESSION_TTL_SECONDS = 3600
+SESSION_TTL_SECONDS = 86400

 def create_session(user_id: int) -> dict:
     return {
`;

export default function TryReviewPage() {
  const [title, setTitle] = useState("");
  const [diff, setDiff] = useState(SAMPLE_DIFF);
  const preview = useReviewPreview();

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!diff.trim()) return;
    preview.mutate({ pr_title: title.trim() || "Untitled diff", diff });
  }

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Try a review</h1>
        <p className="text-sm text-muted">
          Paste a unified diff and run the full 4-step review pipeline (triage →
          deep review → cross-ref → synthesis). When the backend is in mock mode
          the response is deterministic — useful for demos without API keys.
        </p>
      </header>

      <Callout variant="security" title="Privacy & sensitive diffs">
        <p>
          Diffs may contain credentials, tokens, or customer data. Use sample or
          redacted snippets in shared environments. Preview runs are sent to your
          configured Sentinel API — treat the endpoint like any other privileged
          integration.
        </p>
      </Callout>

      <form onSubmit={onSubmit} className="space-y-3">
        <div className="rounded-lg border border-border bg-panel p-4">
          <label className="block text-xs text-muted">PR title (optional)</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Increase session TTL to 24 hours"
            className="mt-1 w-full rounded border border-border bg-panel2 px-3 py-2 text-sm text-fg focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
          />
        </div>

        <div className="rounded-lg border border-border bg-panel p-4">
          <div className="mb-1 flex items-center justify-between">
            <label className="text-xs text-muted">Unified diff</label>
            <button
              type="button"
              onClick={() => setDiff(SAMPLE_DIFF)}
              className="text-xxs text-muted hover:text-fg"
            >
              reset sample
            </button>
          </div>
          <textarea
            value={diff}
            onChange={(e) => setDiff(e.target.value)}
            rows={14}
            className="w-full rounded border border-border bg-panel2 px-3 py-2 font-mono text-xs text-fg focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
            spellCheck={false}
          />
        </div>

        <div className="flex items-center justify-between">
          <div className="text-xxs text-muted">
            Posts to <code className="rounded bg-panel2 px-1">/api/v1/reviews/preview</code>.
            Not persisted to the database.
          </div>
          <button
            type="submit"
            disabled={preview.isPending || !diff.trim()}
            className="rounded bg-accent px-4 py-2 text-sm font-medium text-[#0b0d10] transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg"
          >
            {preview.isPending ? "Reviewing…" : "Run review"}
          </button>
        </div>
      </form>

      {preview.isError && <ErrorPanel error={preview.error} />}

      {preview.data && <PreviewResult data={preview.data} />}
    </div>
  );
}

function PreviewResult({ data }: { data: NonNullable<ReturnType<typeof useReviewPreview>["data"]> }) {
  return (
    <section className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Tile label="Quality score" value={data.pr_quality_score?.toFixed(1) ?? "—"} />
        <Tile label="Comments" value={formatInt(data.comments.length)} />
        <Tile label="Total tokens" value={formatInt(data.total_tokens ?? 0)} />
        <Tile label="Latency" value={formatMs(data.latency_ms ?? 0)} />
        <Tile
          label="Retrieval"
          value={data.retrieval_ms ? formatMs(data.retrieval_ms) : "—"}
        />
      </div>

      <div className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-2 text-sm font-semibold">Summary</h2>
        <p className="text-sm text-fg">{data.summary || "(no summary)"}</p>
        {data.review_focus_areas?.length > 0 && (
          <div className="mt-3">
            <div className="text-xxs uppercase tracking-wide text-muted">
              Focus areas
            </div>
            <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-fg">
              {data.review_focus_areas.map((area, i) => (
                <li key={i}>{area}</li>
              ))}
            </ul>
          </div>
        )}
        <div className="mt-3 flex flex-wrap gap-3 text-xxs text-muted">
          {data.prompt_hash && (
            <span>
              prompt <code className="text-fg">{data.prompt_hash.slice(0, 7)}</code>
            </span>
          )}
          {data.model_version && (
            <span>
              model <code className="text-fg">{data.model_version}</code>
            </span>
          )}
        </div>
      </div>

      <div className="rounded-lg border border-border bg-panel p-4">
        <h2 className="mb-3 text-sm font-semibold">
          Comments ({data.comments.length})
        </h2>
        {data.comments.length === 0 ? (
          <EmptyState
            title="Clean diff — no comments"
            description="The pipeline didn't flag any issues. Try a diff with a concrete bug, security concern, or perf regression."
          />
        ) : (
          <ul className="space-y-3">
            {data.comments.map((c, i) => (
              <CommentRow key={i} comment={c} />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function CommentRow({ comment }: { comment: ReviewCommentOut }) {
  const body =
    (comment as ReviewCommentOut & { body?: string; title?: string }).body ??
    comment.description ??
    "";
  const title = (comment as ReviewCommentOut & { title?: string }).title ?? "";
  return (
    <li className="rounded border border-border bg-panel2 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={comment.severity} />
        <CategoryBadge category={comment.category} />
        <span className="font-mono text-xs text-muted">
          {comment.file_path}:{comment.line_number}
        </span>
        {comment.confidence != null && (
          <span className="ml-auto text-xxs text-muted">
            confidence {(comment.confidence * 100).toFixed(0)}%
          </span>
        )}
      </div>
      {title && <div className="mt-2 text-sm font-medium text-fg">{title}</div>}
      {body && <p className="mt-1 whitespace-pre-wrap text-sm text-fg">{body}</p>}
      {comment.suggestion && (
        <div className="mt-2 rounded bg-panel p-2 text-xs text-fg">
          <span className="font-mono text-xxs uppercase tracking-wide text-accent">
            suggestion
          </span>
          <div className="mt-1 whitespace-pre-wrap font-mono">
            {comment.suggestion}
          </div>
        </div>
      )}
    </li>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border bg-panel px-3 py-3">
      <div className="text-xxs uppercase tracking-wide text-muted">{label}</div>
      <div className="mt-1 font-mono text-xl text-fg">{value}</div>
    </div>
  );
}
