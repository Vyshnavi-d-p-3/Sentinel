"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { Repo, RepoListResponse, RepoSettingsPatch } from "@/lib/types";

export function useReposList(page: number = 1, perPage: number = 50) {
  return useQuery({
    queryKey: ["repos", page, perPage] as const,
    queryFn: () =>
      apiFetch<RepoListResponse>(`/api/v1/repos/?page=${page}&per_page=${perPage}`),
  });
}

export function usePatchRepoSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: RepoSettingsPatch }) => {
      return apiFetch<Repo>(`/api/v1/repos/${id}/settings`, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["repos"] });
    },
  });
}
