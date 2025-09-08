"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  AblationReport,
  EvalRunDetail,
  EvalRunListResponse,
  EvalTriggerResponse,
} from "@/lib/types";

export function useEvalRuns(limit = 50) {
  return useQuery<EvalRunListResponse>({
    queryKey: ["eval-runs", limit] as const,
    queryFn: () => apiFetch<EvalRunListResponse>(`/api/v1/eval/runs?limit=${limit}`),
  });
}

export function useLatestEvalRun() {
  return useQuery<EvalRunDetail>({
    queryKey: ["eval-run-latest"] as const,
    queryFn: () => apiFetch<EvalRunDetail>("/api/v1/eval/runs/latest"),
    retry: false,
  });
}

export function useAblation() {
  return useQuery<AblationReport>({
    queryKey: ["eval-ablation"] as const,
    queryFn: () => apiFetch<AblationReport>("/api/v1/eval/ablation"),
    retry: false,
  });
}

/** Client wait budget — backend subprocess may run up to ``trigger_timeout_sec`` from config. */
const EVAL_TRIGGER_CLIENT_MS_CAP = 900_000;

/** Runs ``eval/scripts/eval_runner.py`` server-side when ``EVAL_TRIGGER_ENABLED=true``. */
export function useEvalTrigger(timeoutSec?: number) {
  const qc = useQueryClient();
  const budgetMs = Math.min(
    EVAL_TRIGGER_CLIENT_MS_CAP,
    Math.ceil((timeoutSec ?? 600) * 1000) + 15_000,
  );
  return useMutation<EvalTriggerResponse, Error, void>({
    mutationFn: () =>
      apiFetch<EvalTriggerResponse>("/api/v1/eval/trigger", {
        method: "POST",
        signal:
          typeof AbortSignal !== "undefined" && "timeout" in AbortSignal
            ? AbortSignal.timeout(budgetMs)
            : undefined,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["eval-runs"] });
      void qc.invalidateQueries({ queryKey: ["eval-run-latest"] });
    },
  });
}
