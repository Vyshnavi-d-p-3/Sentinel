"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type {
  ConfigResponse,
  ReviewCommentOut,
  ReviewPreviewOutput,
  TestGenerationOutput,
} from "@/lib/types";

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

export interface GenerateTestsInput {
  pr_title: string;
  diff: string;
  comments: ReviewCommentOut[];
}

export function useGenerateTests() {
  return useMutation<TestGenerationOutput, Error, GenerateTestsInput>({
    mutationFn: (body) =>
      apiFetch<TestGenerationOutput>("/api/v1/tests/generate", {
        method: "POST",
        body: JSON.stringify({
          pr_title: body.pr_title,
          diff: body.diff,
          comments: body.comments,
        }),
      }),
  });
}
