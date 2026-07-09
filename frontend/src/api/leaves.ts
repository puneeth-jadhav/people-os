import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiEnvelope } from "@/lib/types";

export type RequestType = "leave" | "wfh";
export type RequestStatus = "pending" | "approved" | "rejected" | "cancelled";

export interface LeaveRequestRow {
  id: string;
  employeeId: string;
  employeeName: string;
  requestType: RequestType;
  leaveType: string | null;
  startDate: string;
  endDate: string;
  daysRequested: number | null;
  status: RequestStatus;
  approverId: string | null;
  reason: string | null;
  decisionNote: string | null;
  appliedAt: string | null;
  resolvedAt: string | null;
}

export interface TeamOverlap {
  employeeName: string;
  startDate: string;
  endDate: string;
  requestType: RequestType;
}

export interface CreatedRequest extends LeaveRequestRow {
  teamOverlap: TeamOverlap[];
}

export interface LeaveBalanceRow {
  id: string;
  leaveType: string;
  year: number;
  total: number;
  used: number;
  pending: number;
  carryForward: number;
  remaining: number;
}

export interface ApplyPayload {
  requestType: RequestType;
  startDate: string;
  endDate: string;
  leaveType?: string;
  reason?: string;
}

export interface DecisionPayload {
  requestId: string;
  decisionNote?: string;
}

// --- queries ---

export function useLeaveBalances() {
  return useQuery({
    queryKey: ["leaves", "balances"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<LeaveBalanceRow[]>>(
        "/leaves/balances"
      );
      return res.data.data;
    },
  });
}

export function useMyRequests() {
  return useQuery({
    queryKey: ["leaves", "mine"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<LeaveRequestRow[]>>("/leaves/mine");
      return res.data.data;
    },
  });
}

export function useLeaveQueue() {
  return useQuery({
    queryKey: ["leaves", "queue"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<LeaveRequestRow[]>>(
        "/leaves/queue"
      );
      return res.data.data;
    },
    refetchInterval: 10_000,
  });
}

export function useLeaveCalendar(from?: string, to?: string) {
  return useQuery({
    queryKey: ["leaves", "calendar", from ?? "", to ?? ""],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<LeaveRequestRow[]>>(
        "/leaves/calendar",
        { params: { from, to } }
      );
      return res.data.data;
    },
  });
}

// --- mutations ---

export function useApplyRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ApplyPayload) => {
      const res = await api.post<ApiEnvelope<CreatedRequest>>(
        "/leaves",
        payload
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leaves"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useApproveRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ requestId, decisionNote }: DecisionPayload) => {
      const res = await api.post<ApiEnvelope<LeaveRequestRow>>(
        `/leaves/${requestId}/approve`,
        { decisionNote }
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leaves"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useRejectRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ requestId, decisionNote }: DecisionPayload) => {
      const res = await api.post<ApiEnvelope<LeaveRequestRow>>(
        `/leaves/${requestId}/reject`,
        { decisionNote }
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["leaves"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
