import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiEnvelope } from "@/lib/types";

export interface DashboardHero {
  greeting: string;
  headline: string;
  subtext?: string;
}

export interface ActionItem {
  id: string;
  kind: string;
  title: string;
  subtitle?: string;
  link?: string;
  ageDays?: number;
  contextHint?: string;
  deadline?: string | null;
  waitingOnName?: string;
  amount?: number;
  startDate?: string;
  endDate?: string;
}

export interface QuickAction {
  label: string;
  link: string;
}

export interface LeaveBalance {
  leaveType: string;
  total: number;
  used: number;
  pending: number;
  remaining: number;
}

export interface TeamAvailabilityItem {
  id: string;
  employee: string;
  kind: "leave" | "wfh";
  status: "today" | "upcoming";
  startDate: string;
  endDate: string;
}

export interface OnboardingTaskItem {
  id: string;
  title: string;
  status: "locked" | "unlocked" | "in_progress" | "done";
  owner: string;
  isMine: boolean;
}

export interface OnboardingProgress {
  completed: number;
  total: number;
  percent: number;
  tasks?: OnboardingTaskItem[];
}

export interface OnboardingRunItem {
  id: string;
  employee: string;
  completed: number;
  total: number;
  percent: number;
  startedAt?: string | null;
}

export interface AckStatusItem {
  id: string;
  title: string;
  version: number;
  acked: number;
  total: number;
  percent: number;
}

export type DashboardExperience =
  | "employee"
  | "manager"
  | "hr_admin"
  | "new_hire";

export interface DashboardData {
  role: string;
  experience: DashboardExperience;
  hero: DashboardHero;
  needsAttention?: ActionItem[];
  waitingOnOthers?: ActionItem[];
  upcoming?: ActionItem[];
  recentChanges?: ActionItem[];
  quickActions?: QuickAction[];
  // employee
  leaveBalances?: LeaveBalance[];
  // manager
  teamAvailability?: TeamAvailabilityItem[];
  // new hire
  onboarding?: OnboardingProgress;
  // hr
  onboardingRuns?: OnboardingRunItem[];
  ackStatus?: AckStatusItem[];
  financeQueue?: ActionItem[];
}

async function fetchDashboard(): Promise<DashboardData> {
  const res = await api.get<ApiEnvelope<DashboardData>>("/dashboard");
  return res.data.data;
}

export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
  });
}
