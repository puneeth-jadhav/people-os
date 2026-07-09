import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiEnvelope } from "@/lib/types";

export type TaskStatus = "locked" | "unlocked" | "in_progress" | "done";

export interface OnboardingTask {
  id: string;
  runId: string;
  stepIndex: number;
  title: string;
  ownerId: string | null;
  status: TaskStatus;
  deadlineAt: string | null;
  completedAt: string | null;
  delayed: boolean;
}

export interface OnboardingProgress {
  completed: number;
  total: number;
  percent: number;
}

export interface MyRun {
  id: string;
  status: "in_progress" | "completed";
  startedAt: string | null;
  completedAt: string | null;
  employeeName: string;
  tasks: OnboardingTask[];
  progress: OnboardingProgress;
}

export interface RunRow {
  id: string;
  employeeId: string;
  employeeName: string;
  status: "in_progress" | "completed";
  startedAt: string | null;
  progress: OnboardingProgress;
  tasks: OnboardingTask[];
}

export interface CompletedTask extends OnboardingTask {
  nextTaskId: string | null;
  runCompleted: boolean;
}

export function useMyOnboarding() {
  return useQuery({
    queryKey: ["onboarding", "mine"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<{ run: MyRun | null }>>(
        "/onboarding/mine"
      );
      return res.data.data.run;
    },
  });
}

export function useOnboardingRuns(enabled = true) {
  return useQuery({
    queryKey: ["onboarding", "runs"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<RunRow[]>>("/onboarding/runs");
      return res.data.data;
    },
    enabled,
    refetchInterval: 15_000,
  });
}

export function useCompleteTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { runId: string; taskId: string }) => {
      const res = await api.post<ApiEnvelope<CompletedTask>>(
        `/onboarding/runs/${vars.runId}/tasks/${vars.taskId}/complete`
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["onboarding"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
