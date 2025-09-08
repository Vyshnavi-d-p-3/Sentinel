"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch, qs } from "@/lib/api";
import type { FeedbackEvent, FeedbackStats } from "@/lib/types";

export function useFeedbackStats(opts: { repo_id?: string; days?: number } = {}) {
  const query = qs({ repo_id: opts.repo_id, days: opts.days ?? 30 });
  return useQuery<FeedbackStats>({
    queryKey: ["feedback-stats", opts] as const,
    queryFn: () => apiFetch<FeedbackStats>(`/api/v1/feedback/stats${query}`),
  });
}

export function useRecentFeedback(opts: { repo_id?: string; limit?: number } = {}) {
  const query = qs({ repo_id: opts.repo_id, limit: opts.limit ?? 50 });
  return useQuery<FeedbackEvent[]>({
    queryKey: ["feedback-recent", opts] as const,
    queryFn: () => apiFetch<FeedbackEvent[]>(`/api/v1/feedback/recent${query}`),
  });
}
