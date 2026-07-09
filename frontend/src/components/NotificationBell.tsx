import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  useMarkAllRead,
  useMarkRead,
  useNotifications,
  useUnreadCount,
  type AppNotification,
} from "@/api/notifications";

const FILTERS: { key: string; label: string; match: (t: string) => boolean }[] = [
  { key: "all", label: "All", match: () => true },
  { key: "requests", label: "Requests", match: (t) => t.startsWith("request.") },
  { key: "expenses", label: "Expenses", match: (t) => t.startsWith("expense.") },
  {
    key: "onboarding",
    label: "Onboarding",
    match: (t) => t.startsWith("onboarding."),
  },
  { key: "policy", label: "Policy", match: (t) => t.startsWith("policy.") },
];

function timeAgo(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  const secs = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (secs < 60) return "just now";
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [filterKey, setFilterKey] = useState("all");
  const navigate = useNavigate();
  const { data: unread } = useUnreadCount();
  const { data: notifications } = useNotifications();
  const markRead = useMarkRead();
  const markAll = useMarkAllRead();

  const filter = FILTERS.find((f) => f.key === filterKey) ?? FILTERS[0];
  const visible = useMemo(
    () => (notifications ?? []).filter((n) => filter.match(n.type)),
    [notifications, filter]
  );

  const onClickNotification = (n: AppNotification) => {
    if (!n.read) markRead.mutate(n.id);
    setOpen(false);
    if (n.link) navigate(n.link);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="relative flex h-9 w-9 items-center justify-center rounded-full border border-line bg-card text-navy transition hover:bg-white hover:shadow-sm"
        aria-label="Notifications"
      >
        🔔
        {unread && unread > 0 ? (
          <span className="absolute -right-1 -top-1 flex h-[15px] min-w-[15px] items-center justify-center rounded-lg bg-clay px-1 font-mono text-[9px] font-semibold text-white">
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <div className="absolute bottom-full left-0 z-20 mb-2 w-96 rounded border border-line bg-card shadow-md">
          <div className="flex items-center justify-between border-b border-line px-4 py-2">
            <span className="font-mono text-[10px] uppercase tracking-[1.5px] text-inkSoft">
              Notifications
            </span>
            <button
              onClick={() => markAll.mutate()}
              disabled={markAll.isPending}
              className="text-xs font-medium text-inkSoft hover:text-ink"
            >
              Mark all read
            </button>
          </div>
          <div className="flex flex-wrap gap-1 border-b border-line px-3 py-2">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setFilterKey(f.key)}
                className={
                  "rounded-full px-2 py-0.5 text-xs font-medium " +
                  (filterKey === f.key
                    ? "bg-navy text-paper"
                    : "bg-paper2 text-inkSoft hover:bg-line")
                }
              >
                {f.label}
              </button>
            ))}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {visible.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-inkSoft">
                No notifications.
              </p>
            ) : (
              visible.map((n) => (
                <button
                  key={n.id}
                  onClick={() => onClickNotification(n)}
                  className={
                    "block w-full border-b border-line px-4 py-3 text-left transition hover:bg-paper2 " +
                    (n.read ? "" : "bg-paper2/50")
                  }
                >
                  <div className="flex items-start gap-2">
                    {!n.read ? (
                      <span className="mt-1.5 h-2 w-2 flex-shrink-0 rounded-full bg-navy2" />
                    ) : (
                      <span className="mt-1.5 h-2 w-2 flex-shrink-0" />
                    )}
                    <div className="min-w-0">
                      <p
                        className={
                          "truncate text-sm " +
                          (n.read
                            ? "text-inkSoft"
                            : "font-semibold text-ink")
                        }
                      >
                        {n.title}
                      </p>
                      {n.body ? (
                        <p className="mt-0.5 line-clamp-2 text-xs text-inkSoft">
                          {n.body}
                        </p>
                      ) : null}
                      <p className="mt-0.5 text-[11px] text-inkSoft">
                        {timeAgo(n.createdAt)}
                        {n.link ? " · tap to open" : ""}
                      </p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
