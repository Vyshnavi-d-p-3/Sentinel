"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

export function useHealth() {
  return useQuery<HealthResponse>({
    queryKey: ["health"] as const,
    queryFn: () => apiFetch<HealthResponse>("/health"),
    refetchInterval: 30_000,
  });
}
