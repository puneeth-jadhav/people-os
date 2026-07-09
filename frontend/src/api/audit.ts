import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiEnvelope } from "@/lib/types";

export interface AuditRow {
  id: string;
  actorId: string | null;
  actorName: string;
  action: string;
  resourceType: string | null;
  resourceId: string | null;
  metadata: Record<string, unknown> | null;
  createdAt: string | null;
}

export interface AuditFilter {
  action?: string;
  resourceType?: string;
}

export function useAuditLog(filter: AuditFilter = {}) {
  return useQuery({
    queryKey: ["audit", filter.action ?? "", filter.resourceType ?? ""],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<AuditRow[]>>("/audit", {
        params: {
          action: filter.action || undefined,
          resource_type: filter.resourceType || undefined,
        },
      });
      return res.data.data;
    },
  });
}

export async function downloadAuditCsv(filter: AuditFilter = {}): Promise<void> {
  const res = await api.get("/audit/export", {
    params: {
      action: filter.action || undefined,
      resource_type: filter.resourceType || undefined,
    },
    responseType: "blob",
  });
  const blob = new Blob([res.data as BlobPart], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "audit_log.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
