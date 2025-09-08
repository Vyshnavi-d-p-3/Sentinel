"use client";

import { useEffect, useMemo, useState } from "react";
import { useActivatePrompt, usePrompt, usePromptDiff, usePrompts } from "@/hooks/prompts";
import { EmptyState, ErrorPanel, LoadingBar } from "@/components/empty";
import { formatRelativeTime } from "@/lib/format";
import type { PromptSummary } from "@/lib/types";

function shortHash(hash: string | null | undefined): string {
  if (!hash) return "—";
  return `${hash.slice(0, 7)}${hash.length > 7 ? "…" : ""}`;
}

export default function PromptsPage() {
  const list = usePrompts();
  const [selected, setSelected] = useState<string | null>(null);
  const [compareTo, setCompareTo] = useState<string | null>(null);

  useEffect(() => {
    if (!selected && list.data?.active) setSelected(list.data.active.hash);
  }, [list.data, selected]);

  if (list.isLoading) return <LoadingBar />;
  if (list.isError) return <ErrorPanel error={list.error} />;
  if (!list.data) return null;

  const prompts = list.data.prompts;
  const activeHash = list.data.active?.hash ?? null;

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Prompts</h1>
        <p className="text-sm text-muted">
          Versioned review-pipeline prompts. Every persisted review pins the exact hash
          that generated it — flip the active version here, and the diff view shows
          what changed.
        </p>
      </header>

      {prompts.length === 0 ? (
        <EmptyState
          title="No prompts indexed"
          description="Add rows to the prompts table or let the review pipeline seed one on next run."
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
          <aside className="space-y-1 rounded-lg border border-border bg-panel p-2">
            {prompts.map((p) => (
              <PromptListItem
                key={p.hash}
                prompt={p}
                selected={selected === p.hash}
                activeHash={activeHash}
                onSelect={() => setSelected(p.hash)}
                onCompare={() => setCompareTo(p.hash === compareTo ? null : p.hash)}
                isCompareTarget={compareTo === p.hash}
              />
            ))}
          </aside>

          <main className="min-w-0 space-y-4">
            {selected ? (
              <PromptCard
                hash={selected}
                comparedTo={compareTo && compareTo !== selected ? compareTo : null}
                onSelectCompare={setCompareTo}
                prompts={prompts}
                activeHash={activeHash}
              />
            ) : (
              <p className="text-sm text-muted">Select a prompt from the list.</p>
            )}
          </main>
        </div>
      )}
    </div>
  );
}

function PromptListItem({
  prompt,
  selected,
  activeHash,
  onSelect,
  onCompare,
  isCompareTarget,
}: {
  prompt: PromptSummary;
  selected: boolean;
  activeHash: string | null;
  onSelect: () => void;
  onCompare: () => void;
  isCompareTarget: boolean;
}) {
  const isActive = prompt.hash === activeHash;
  return (
    <button
      onClick={onSelect}
      onDoubleClick={onCompare}
      className={`block w-full rounded-md px-3 py-2 text-left text-sm transition-colors ${
        selected ? "bg-panel2" : "hover:bg-panel2/60"
      }`}
    >
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-fg">{shortHash(prompt.hash)}</span>
        {isActive && (
          <span className="rounded bg-ok/20 px-1.5 py-0.5 text-xxs font-medium text-ok">
            active
          </span>
        )}
        {isCompareTarget && (
          <span className="rounded bg-accent/20 px-1.5 py-0.5 text-xxs font-medium text-accent">
            diff
          </span>
        )}
        <span className="ml-auto text-xxs text-muted">{prompt.source}</span>
      </div>
      <div className="mt-0.5 truncate text-xs text-muted">
        {prompt.name} · v{prompt.version}
      </div>
      {prompt.created_at && (
        <div className="mt-0.5 text-xxs text-muted">
          {formatRelativeTime(prompt.created_at)}
        </div>
      )}
    </button>
  );
}

function PromptCard({
  hash,
  comparedTo,
  onSelectCompare,
  prompts,
  activeHash,
}: {
  hash: string;
  comparedTo: string | null;
  onSelectCompare: (h: string | null) => void;
  prompts: PromptSummary[];
  activeHash: string | null;
}) {
  const detail = usePrompt(hash);
  const diff = usePromptDiff(hash, comparedTo);
  const activate = useActivatePrompt();

  const isActive = hash === activeHash;
  const prompt = detail.data;
  const compareOptions = useMemo(
    () => prompts.filter((p) => p.hash !== hash),
    [prompts, hash],
  );

  if (detail.isLoading) return <LoadingBar />;
  if (detail.isError) return <ErrorPanel error={detail.error} />;
  if (!prompt) return null;

  const canActivate = prompt.source === "db" && !isActive;

  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-border bg-panel p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="font-mono text-sm text-fg">{prompt.hash}</h2>
            <div className="mt-1 text-xs text-muted">
              {prompt.name} · v{prompt.version} · source {prompt.source}
              {prompt.created_at ? ` · ${formatRelativeTime(prompt.created_at)}` : ""}
            </div>
            {prompt.description && (
              <p className="mt-2 max-w-2xl text-sm text-fg">{prompt.description}</p>
            )}
          </div>
          <div className="flex flex-col items-end gap-2">
            {isActive ? (
              <span className="rounded bg-ok/20 px-2 py-1 text-xs font-medium text-ok">
                currently active
              </span>
            ) : (
              <button
                onClick={() => canActivate && activate.mutate(hash)}
                disabled={!canActivate || activate.isPending}
                className="rounded bg-accent px-3 py-1 text-xs font-medium text-bg disabled:cursor-not-allowed disabled:opacity-40"
                title={
                  prompt.source === "code"
                    ? "Code-bundled prompts can't be deactivated — rebuild the deploy instead."
                    : "Activate this prompt"
                }
              >
                {activate.isPending ? "Activating…" : "Activate"}
              </button>
            )}
            {activate.isError && (
              <span className="text-xxs text-bad">
                {(activate.error as Error).message}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-panel p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">Diff vs.</h3>
          <select
            value={comparedTo ?? ""}
            onChange={(e) => onSelectCompare(e.target.value || null)}
            className="rounded border border-border bg-panel2 px-2 py-1 text-xs text-fg"
          >
            <option value="">— select a version —</option>
            {compareOptions.map((p) => (
              <option key={p.hash} value={p.hash}>
                {shortHash(p.hash)} · {p.name} v{p.version}
              </option>
            ))}
          </select>
        </div>

        {!comparedTo ? (
          <p className="text-sm text-muted">Pick another version above to diff.</p>
        ) : diff.isLoading ? (
          <LoadingBar />
        ) : diff.isError ? (
          <ErrorPanel error={diff.error} />
        ) : !diff.data?.diffs.length ? (
          <p className="text-sm text-muted">Identical — no textual differences.</p>
        ) : (
          <div className="space-y-4">
            {diff.data.diffs.map((entry) => (
              <div key={entry.field} className="rounded border border-border bg-panel2 p-3">
                <div className="mb-2 flex items-center justify-between text-xs text-muted">
                  <span className="font-mono">{entry.field}</span>
                  <span>
                    <span className="text-ok">+{entry.added_lines}</span>{" "}
                    <span className="text-bad">-{entry.removed_lines}</span>
                  </span>
                </div>
                <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs leading-relaxed">
                  {entry.unified_diff.split("\n").map((line, i) => (
                    <div
                      key={i}
                      className={
                        line.startsWith("+") && !line.startsWith("+++")
                          ? "text-ok"
                          : line.startsWith("-") && !line.startsWith("---")
                            ? "text-bad"
                            : line.startsWith("@@")
                              ? "text-accent"
                              : "text-muted"
                      }
                    >
                      {line || "\u00A0"}
                    </div>
                  ))}
                </pre>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="rounded-lg border border-border bg-panel p-4">
        <h3 className="mb-3 text-sm font-semibold">System prompt</h3>
        <pre className="max-h-96 overflow-auto whitespace-pre-wrap break-words rounded bg-panel2 p-3 text-xs leading-relaxed text-fg">
          {prompt.system_prompt}
        </pre>
      </div>

      <div className="rounded-lg border border-border bg-panel p-4">
        <h3 className="mb-3 text-sm font-semibold">User template</h3>
        <pre className="max-h-60 overflow-auto whitespace-pre-wrap break-words rounded bg-panel2 p-3 text-xs leading-relaxed text-muted">
          {prompt.user_template}
        </pre>
      </div>
    </div>
  );
}
