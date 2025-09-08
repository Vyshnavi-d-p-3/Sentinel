"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch, qs } from "@/lib/api";
import type {
  PromptDetail,
  PromptDiffResponse,
  PromptListResponse,
  PromptSummary,
} from "@/lib/types";

export function usePrompts() {
  return useQuery<PromptListResponse>({
    queryKey: ["prompts"] as const,
    queryFn: () => apiFetch<PromptListResponse>("/api/v1/prompts/"),
  });
}

export function usePrompt(hash: string | null) {
  return useQuery<PromptDetail>({
    queryKey: ["prompt", hash] as const,
    enabled: !!hash,
    queryFn: () => apiFetch<PromptDetail>(`/api/v1/prompts/${hash}`),
  });
}

export function usePromptDiff(a: string | null, b: string | null) {
  const query = qs({ against: b ?? undefined });
  return useQuery<PromptDiffResponse>({
    queryKey: ["prompt-diff", a, b] as const,
    enabled: !!(a && b && a !== b),
    queryFn: () => apiFetch<PromptDiffResponse>(`/api/v1/prompts/${a}/diff${query}`),
  });
}

export function useActivatePrompt() {
  const qc = useQueryClient();
  return useMutation<PromptSummary, Error, string>({
    mutationFn: (hash) =>
      apiFetch<PromptSummary>(`/api/v1/prompts/activate/${hash}`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });
}
