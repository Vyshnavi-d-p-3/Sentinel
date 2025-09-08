"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { ConfigResponse, ReviewPreviewOutput } from "@/lib/types";

export function useConfig() {
  return useQuery<ConfigResponse>({
    queryKey: ["config"] as const,
    queryFn: () => apiFetch<ConfigResponse>("/api/v1/config/"),
  });
}

export interface ReviewPreviewInput {
  pr_title: string;
  diff: string;
  repo_id?: string;
  pr_number?: number;
}

export function useReviewPreview() {
  return useMutation<ReviewPreviewOutput, Error, ReviewPreviewInput>({
    mutationFn: (body) =>
      apiFetch<ReviewPreviewOutput>("/api/v1/reviews/preview", {
        method: "POST",
        body: JSON.stringify({
          repo_id: body.repo_id ?? "local-preview",
          pr_number: body.pr_number ?? 0,
          pr_title: body.pr_title,
          diff: body.diff,
        }),
      }),
  });
}
