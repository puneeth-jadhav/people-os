import { useQuery } from "@tanstack/react-query";
import { AxiosError } from "axios";
import { api } from "@/lib/api";
import type { ApiEnvelope } from "@/lib/types";
import type { RequestType, RequestStatus, TeamOverlap } from "@/api/leaves";

export interface HistoryRequest {
  id: string;
  requestType: RequestType;
  leaveType: string | null;
  startDate: string;
  endDate: string;
  days: number | null;
  status: RequestStatus;
  reason: string | null;
}

export interface HistoryBalance {
  leaveType: string;
  total: number;
  used: number;
  pending: number;
  remaining: number;
}

export interface RequestHistory {
  requests: HistoryRequest[];
  totalsByType: Record<string, number>;
  balance: HistoryBalance[];
  anomalyFlags: string[];
  teamOverlap: TeamOverlap[];
}

export interface HistoryParams {
  months?: number;
  overlapStart?: string;
  overlapEnd?: string;
}

export function useRequestHistory(
  employeeId: string | null | undefined,
  { months, overlapStart, overlapEnd }: HistoryParams = {}
) {
  return useQuery<RequestHistory, AxiosError>({
    queryKey: [
      "requestHistory",
      employeeId ?? "",
      months ?? "",
      overlapStart ?? "",
      overlapEnd ?? "",
    ],
    enabled: Boolean(employeeId),
    retry: (_count, err) => {
      // Do not retry on auth/permission errors.
      const status = err?.response?.status;
      if (status === 403 || status === 404 || status === 401) return false;
      return _count < 2;
    },
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<RequestHistory>>(
        `/requests/history/${employeeId}`,
        { params: { months, overlapStart, overlapEnd } }
      );
      return res.data.data;
    },
  });
}
