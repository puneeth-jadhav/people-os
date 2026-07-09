import { useRequestHistory } from "@/api/requestHistory";
import { extractErrorMessage } from "@/lib/api";
import type { HistoryRequest } from "@/api/requestHistory";

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    approved: "bg-moss/15 text-moss",
    pending: "bg-ochre/15 text-ochre",
    rejected: "bg-clay/15 text-clay",
    cancelled: "bg-paper2 text-inkSoft",
  };
  return (
    <span
      className={
        "rounded-full px-2 py-0.5 font-mono text-[10px] font-medium uppercase " +
        (map[status] || "bg-paper2 text-inkSoft")
      }
    >
      {status}
    </span>
  );
}

function HistoryRow({ r }: { r: HistoryRequest }) {
  const isWfh = r.requestType === "wfh";
  return (
    <div
      className={
        "flex items-center justify-between rounded border px-3 py-2 text-sm " +
        (isWfh
          ? "border-navy2/40 bg-navy2/5"
          : "border-line bg-card")
      }
    >
      <div className="flex items-center gap-2">
        <span
          className={
            "rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase " +
            (isWfh
              ? "bg-navy2/15 text-navy2"
              : "bg-navy/10 text-navy")
          }
        >
          {isWfh ? "WFH" : r.leaveType || "leave"}
        </span>
        <span className="text-ink">
          {r.startDate} → {r.endDate}
          {r.days ? ` (${r.days}d)` : ""}
        </span>
        {r.reason ? (
          <span className="hidden text-inkSoft sm:inline">· {r.reason}</span>
        ) : null}
      </div>
      <StatusBadge status={r.status} />
    </div>
  );
}

export interface RequestHistoryPanelProps {
  employeeId: string;
  months?: number;
  overlapStart?: string;
  overlapEnd?: string;
}

export default function RequestHistoryPanel({
  employeeId,
  months = 6,
  overlapStart,
  overlapEnd,
}: RequestHistoryPanelProps) {
  const { data, isLoading, error } = useRequestHistory(employeeId, {
    months,
    overlapStart,
    overlapEnd,
  });

  if (isLoading) {
    return (
      <div className="rounded border border-line bg-paper p-4 text-sm text-inkSoft">
        Loading history…
      </div>
    );
  }

  if (error) {
    const status = error.response?.status;
    const msg =
      status === 403
        ? "You are not authorized to view this employee's history."
        : extractErrorMessage(error);
    return (
      <div className="rounded border border-clay/40 bg-clay/10 p-4 text-sm text-clay">
        {msg}
      </div>
    );
  }

  if (!data) return null;

  const totals = Object.entries(data.totalsByType);

  return (
    <div className="space-y-4 rounded border border-line bg-paper p-4">
      <div>
        <h4 className="font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-inkSoft">
          Anomaly flags
        </h4>
        {data.anomalyFlags.length === 0 ? (
          <p className="mt-1 text-sm text-inkSoft">None detected.</p>
        ) : (
          <div className="mt-1 flex flex-wrap gap-2">
            {data.anomalyFlags.map((f) => (
              <span
                key={f}
                className="rounded-full bg-ochre/15 px-2.5 py-1 text-xs font-medium text-ochre"
              >
                ⚠ {f}
              </span>
            ))}
          </div>
        )}
      </div>

      {overlapStart && overlapEnd ? (
        <div>
          <h4 className="font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-inkSoft">
            Team overlap ({overlapStart} → {overlapEnd})
          </h4>
          {data.teamOverlap.length === 0 ? (
            <p className="mt-1 text-sm text-inkSoft">
              No teammates are away on these dates.
            </p>
          ) : (
            <ul className="mt-1 space-y-1">
              {data.teamOverlap.map((t, i) => (
                <li key={i} className="text-sm text-inkSoft">
                  <span className="font-medium text-ink">{t.employeeName}</span> —{" "}
                  {t.requestType === "wfh" ? "WFH" : "Leave"} {t.startDate} →{" "}
                  {t.endDate}
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      <div>
        <h4 className="font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-inkSoft">
          Totals ({months}mo, approved)
        </h4>
        {totals.length === 0 ? (
          <p className="mt-1 text-sm text-inkSoft">No approved days.</p>
        ) : (
          <div className="mt-1 flex flex-wrap gap-2">
            {totals.map(([k, v]) => (
              <span
                key={k}
                className="rounded bg-card px-2.5 py-1 text-xs text-ink ring-1 ring-line"
              >
                {k}: <span className="font-semibold">{v}d</span>
              </span>
            ))}
          </div>
        )}
      </div>

      <div>
        <h4 className="font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-inkSoft">
          Current balances
        </h4>
        {data.balance.length === 0 ? (
          <p className="mt-1 text-sm text-inkSoft">No balances on record.</p>
        ) : (
          <div className="mt-1 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {data.balance.map((b) => (
              <div
                key={b.leaveType}
                className="rounded bg-card px-3 py-2 text-xs ring-1 ring-line"
              >
                <div className="font-medium capitalize text-ink">
                  {b.leaveType}
                </div>
                <div className="text-inkSoft">
                  {b.remaining} left · {b.used} used · {b.pending} pending
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <h4 className="font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-inkSoft">
          History ({months} months)
        </h4>
        {data.requests.length === 0 ? (
          <p className="mt-1 text-sm text-inkSoft">No requests in range.</p>
        ) : (
          <div className="mt-1 max-h-64 space-y-1.5 overflow-y-auto pr-1">
            {data.requests.map((r) => (
              <HistoryRow key={r.id} r={r} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
