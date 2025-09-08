"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch, qs } from "@/lib/api";
import type { CostDailyRow, CostSummary } from "@/lib/types";

export function useCostSummary(opts: { repo_id?: string; range?: string } = {}) {
  const query = qs({ repo_id: opts.repo_id, range: opts.range ?? "7d" });
  return useQuery<CostSummary>({
    queryKey: ["cost-summary", opts] as const,
    queryFn: () => apiFetch<CostSummary>(`/api/v1/costs/summary${query}`),
  });
}

export function useDailyCosts(opts: { repo_id?: string; days?: number } = {}) {
  const query = qs({ repo_id: opts.repo_id, days: opts.days ?? 30 });
  return useQuery<CostDailyRow[]>({
    queryKey: ["cost-daily", opts] as const,
    queryFn: () => apiFetch<CostDailyRow[]>(`/api/v1/costs/daily${query}`),
  });
}
