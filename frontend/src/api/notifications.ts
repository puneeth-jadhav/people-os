import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiEnvelope } from "@/lib/types";

export interface AppNotification {
  id: string;
  type: string;
  title: string;
  body: string | null;
  link: string | null;
  resourceType: string | null;
  resourceId: string | null;
  read: boolean;
  createdAt: string | null;
}

export interface NotificationFilter {
  type?: string;
  unread?: boolean;
}

export function useNotifications(filter: NotificationFilter = {}) {
  return useQuery({
    queryKey: ["notifications", "list", filter.type ?? "", filter.unread ?? false],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<AppNotification[]>>(
        "/notifications",
        {
          params: {
            type: filter.type || undefined,
            unread: filter.unread ? "true" : undefined,
          },
        }
      );
      return res.data.data;
    },
    refetchInterval: 10_000,
  });
}

export function useUnreadCount() {
  return useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<{ count: number }>>(
        "/notifications/unread-count"
      );
      return res.data.data.count;
    },
    refetchInterval: 10_000,
  });
}

export function useMarkRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.patch<ApiEnvelope<AppNotification>>(
        `/notifications/${id}`,
        { read: true }
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}

export function useMarkAllRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await api.post<ApiEnvelope<{ updated: number }>>(
        "/notifications/read-all"
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications"] });
    },
  });
}
