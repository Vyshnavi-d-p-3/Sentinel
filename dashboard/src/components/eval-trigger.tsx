"use client";

import { Callout } from "@/components/callout";
import { ErrorPanel } from "@/components/empty";
import { useConfig } from "@/hooks/config";
import { useEvalTrigger } from "@/hooks/eval";
import { formatInt } from "@/lib/format";
import clsx from "clsx";

export function EvalTriggerPanel() {
  const config = useConfig();
  const timeoutSec = Math.ceil(config.data?.eval.trigger_timeout_sec ?? 600);
  const trigger = useEvalTrigger(timeoutSec);

  const harness = config.data?.eval;
  const enabled = harness?.remote_trigger_enabled ?? false;

  return (
    <section className="space-y-3 rounded-lg border border-border bg-panel p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold">Run harness on server</h2>
          <p className="max-w-2xl text-xs text-muted">
            Executes the same entrypoint as CI (<code className="rounded bg-panel2 px-1">eval/scripts/eval_runner.py</code>)
            and refreshes metrics below. Disabled unless the API sets{" "}
            <code className="rounded bg-panel2 px-1">EVAL_TRIGGER_ENABLED=true</code>.
          </p>
        </div>
        <button
          type="button"
          disabled={config.isLoading || !enabled || trigger.isPending}
          title={
            !enabled
              ? "Enable EVAL_TRIGGER_ENABLED on the Sentinel backend"
              : "Run eval_runner.py with fixtures under eval/fixtures"
          }
          onClick={() => trigger.mutate()}
          className={clsx(
            "shrink-0 rounded px-4 py-2 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-panel",
            enabled && !trigger.isPending
              ? "bg-accent text-[#0b0d10] hover:bg-accent/90"
              : "cursor-not-allowed bg-panel2 text-muted opacity-70",
          )}
        >
          {trigger.isPending ? "Running eval…" : "Run eval now"}
        </button>
      </div>

      {harness && (
        <p className="text-xxs text-muted">
          Mock LLM in subprocess:{" "}
          <span className="text-fg">{harness.trigger_force_mock ? "yes" : "no"}</span>
          {" · "}
          Timeout:{" "}
          <span className="font-mono text-fg">{Math.round(harness.trigger_timeout_sec)}s</span>
        </p>
      )}

      {!config.isLoading && !enabled && (
        <Callout variant="warning" title="Remote trigger is off">
          <p>
            Set <code className="text-warn">EVAL_TRIGGER_ENABLED=true</code> on the backend, restart
            the API, and refresh Settings. Keep <code className="text-warn">API_KEY</code> set in
            production — this endpoint is rate-limited but expensive.
          </p>
        </Callout>
      )}

      {trigger.isSuccess && trigger.data && (
        <Callout
          variant={trigger.data.regression_gate_failed ? "warning" : "success"}
          title={
            trigger.data.regression_gate_failed
              ? "Eval finished — regression gate reported a drop"
              : "Eval finished"
          }
        >
          <ul className="list-inside list-disc space-y-1 text-sm">
            <li>
              Exit code <span className="font-mono">{trigger.data.exit_code}</span>
              {trigger.data.stderr_tail ? " (see stderr tail on failure)" : ""}
            </li>
            <li className="font-mono text-xxs break-all">{trigger.data.results_path}</li>
            {trigger.data.summary && (
              <li>
                Overall F1{" "}
                <span className="font-mono text-ok">
                  {trigger.data.summary.overall_f1?.toFixed(3) ?? "—"}
                </span>
                {" · "}
                PRs {formatInt(trigger.data.summary.total_prs_evaluated)}
              </li>
            )}
          </ul>
          {trigger.data.stderr_tail && (
            <pre className="mt-2 max-h-40 overflow-auto rounded bg-panel2 p-2 font-mono text-xxs text-muted">
              {trigger.data.stderr_tail}
            </pre>
          )}
        </Callout>
      )}

      {trigger.isError && <ErrorPanel error={trigger.error} />}
    </section>
  );
}
