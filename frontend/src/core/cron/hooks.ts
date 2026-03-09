import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { deleteCronJob, listCronJobs, toggleCronJob, upsertCronJob } from "./api";
import type { CronJob } from "./types";

const QUERY_KEY = ["cron-jobs"];

export function useCronJobs() {
  const { data, isLoading, error } = useQuery<CronJob[]>({
    queryKey: QUERY_KEY,
    queryFn: listCronJobs,
    refetchOnWindowFocus: false,
    retry: false,
  });
  return { jobs: data ?? [], isLoading: isLoading && !error, error };
}

export function useUpsertCronJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (job: CronJob) => upsertCronJob(job),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function useDeleteCronJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => deleteCronJob(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}

export function useToggleCronJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => toggleCronJob(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });
}
