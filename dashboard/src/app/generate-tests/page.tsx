"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CategoryBadge } from "@/components/badges";
import { Callout } from "@/components/callout";
import { EmptyState, ErrorPanel } from "@/components/empty";
import { apiFetch } from "@/lib/api";
import type { ReviewCommentOut, TestGenerationOutput } from "@/lib/types";

const SAMPLE_DIFF = `diff --git a/app/db.py b/app/db.py
--- a/app/db.py
+++ b/app/db.py
@@ -8,4 +8,4 @@ def get_user(name):
-    return db.execute(f"SELECT * FROM users WHERE name = '{name}'")
+    return db.execute("SELECT * FROM users WHERE name = %s", (name,))
`;

const SAMPLE_COMMENTS: ReviewCommentOut[] = [
  {
    file_path: "app/db.py",
    line_number: 9,
    category: "security",
    severity: "high",
    description: "SQL query uses string interpolation with untrusted input.",
    suggestion: "Use parameterized queries.",
    confidence: 0.92,
  },
];

export default function GenerateTestsPage() {
  const [title, setTitle] = useState("Fix unsafe SQL query");
  const [diff, setDiff] = useState(SAMPLE_DIFF);
  const [commentsJson, setCommentsJson] = useState(
    JSON.stringify(SAMPLE_COMMENTS, null, 2),
  );
  const [copied, setCopied] = useState<string | null>(null);
  const generate = useMutation<
    TestGenerationOutput,
    Error,
    { pr_title: string; diff: string; comments: ReviewCommentOut[] }
  >({
    mutationFn: (body) =>
      apiFetch<TestGenerationOutput>("/api/v1/tests/generate", {
        method: "POST",
        body: JSON.stringify(body),
      }),
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!diff.trim()) return;
    const comments = JSON.parse(commentsJson) as ReviewCommentOut[];
    generate.mutate({
      pr_title: title,
      diff,
      comments,
    });
  }

  async function copyCode(name: string, code: string) {
    await navigator.clipboard.writeText(code);
    setCopied(name);
    setTimeout(() => setCopied(null), 1200);
  }

  function frameworkIcon(framework: string) {
    if (framework === "pytest" || framework === "unittest") return "🐍";
    if (framework === "jest") return "🟨";
    if (framework === "vitest") return "⚡";
    if (framework === "mocha") return "☕";
    return "🧪";
  }

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Generate Tests</h1>
        <p className="text-sm text-muted">
          Step 5 Smart Test Generator turns eligible review findings into runnable
          regression tests.
        </p>
      </header>

      <Callout variant="security" title="Input format">
        <p>
          Provide a unified diff plus review comments JSON. Only security, bug,
          and performance findings with severity medium or higher are eligible.
        </p>
      </Callout>

      <form onSubmit={onSubmit} className="space-y-3">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className="w-full rounded border border-border bg-panel2 px-3 py-2 text-sm text-fg focus:border-accent focus:outline-none"
          placeholder="PR title"
        />

        <textarea
          value={diff}
          onChange={(e) => setDiff(e.target.value)}
          rows={10}
          className="w-full rounded border border-border bg-panel2 px-3 py-2 font-mono text-xs text-fg focus:border-accent focus:outline-none"
          spellCheck={false}
        />

        <textarea
          value={commentsJson}
          onChange={(e) => setCommentsJson(e.target.value)}
          rows={12}
          className="w-full rounded border border-border bg-panel2 px-3 py-2 font-mono text-xs text-fg focus:border-accent focus:outline-none"
          spellCheck={false}
        />

        <button
          type="submit"
          disabled={generate.isPending || !diff.trim()}
          className="rounded bg-accent px-4 py-2 text-sm font-medium text-[#0b0d10] transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {generate.isPending ? "Generating…" : "Generate Tests"}
        </button>
      </form>

      {generate.isError && <ErrorPanel error={generate.error} />}

      {generate.data && (
        <section className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Tile label="Tests generated" value={String(generate.data.total_generated)} />
            <Tile label="Eligible comments" value={String(generate.data.total_eligible)} />
            <Tile label="Tokens used" value={String(generate.data.tokens_used ?? 0)} />
            <Tile label="Latency (ms)" value={String(generate.data.latency_ms ?? 0)} />
          </div>

          {generate.data.tests.length === 0 ? (
            <EmptyState
              title="No tests generated"
              description={generate.data.skipped_reasons.join(" ") || "No eligible findings."}
            />
          ) : (
            <ul className="space-y-3">
              {generate.data.tests.map((t, idx) => (
                <li key={`${t.test_name}-${idx}`} className="rounded border border-border bg-panel p-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{frameworkIcon(t.framework)}</span>
                    <div className="text-sm font-semibold">{t.test_name}</div>
                    <CategoryBadge category={t.category} />
                    <span className="ml-auto text-xs text-muted">{t.framework}</span>
                  </div>
                  <div className="mt-1 text-xs text-muted">{t.test_file_path}</div>
                  <p className="mt-2 text-sm text-fg">{t.description}</p>
                  <div className="mt-2 flex justify-end">
                    <button
                      type="button"
                      onClick={() => copyCode(t.test_name, t.test_code)}
                      className="rounded border border-border px-2 py-1 text-xs text-muted hover:text-fg"
                    >
                      {copied === t.test_name ? "Copied" : "Copy"}
                    </button>
                  </div>
                  <pre className="language-python mt-2 overflow-x-auto rounded bg-panel2 p-3 text-xs text-fg">
                    <code>{t.test_code}</code>
                  </pre>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
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
