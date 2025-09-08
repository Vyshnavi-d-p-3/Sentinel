"use client";

import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { apiFetch, qs } from "@/lib/api";
import type {
  ReviewDetailResponse,
  ReviewListResponse,
} from "@/lib/types";

export interface ReviewsQueryParams {
  repo_id?: string;
  status?: string;
  category?: string;
  severity?: string;
  page?: number;
  per_page?: number;
}

export function useReviews(params: ReviewsQueryParams) {
  const query = qs({
    repo_id: params.repo_id,
    status: params.status,
    category: params.category,
    severity: params.severity,
    page: params.page ?? 1,
    per_page: params.per_page ?? 20,
  });

  return useQuery<ReviewListResponse>({
    queryKey: ["reviews", params] as const,
    queryFn: () => apiFetch<ReviewListResponse>(`/api/v1/reviews/${query}`),
    placeholderData: keepPreviousData,
  });
}

export function useReview(reviewId: string | null) {
  return useQuery<ReviewDetailResponse>({
    queryKey: ["review", reviewId] as const,
    queryFn: () =>
      apiFetch<ReviewDetailResponse>(`/api/v1/reviews/${reviewId}`),
    enabled: Boolean(reviewId),
  });
}
