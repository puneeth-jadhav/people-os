import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import PageShell from "@/components/PageShell";
import RequestHistoryPanel from "@/components/RequestHistoryPanel";
import { extractErrorMessage } from "@/lib/api";
import {
  useApproveRequest,
  useLeaveQueue,
  useRejectRequest,
  type LeaveRequestRow,
} from "@/api/leaves";

function TypeBadge({ requestType }: { requestType: string }) {
  const isWfh = requestType === "wfh";
  return (
    <span
      className={
        "rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold uppercase " +
        (isWfh ? "bg-navy2/15 text-navy2" : "bg-navy/10 text-navy")
      }
    >
      {isWfh ? "WFH" : "Leave"}
    </span>
  );
}

function QueueRow({
  row,
  expanded,
  onToggle,
}: {
  row: LeaveRequestRow;
  expanded: boolean;
  onToggle: () => void;
}) {
  const [note, setNote] = useState("");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const approve = useApproveRequest();
  const reject = useRejectRequest();
  const busy = approve.isPending || reject.isPending;

  const doApprove = () => {
    setErrorMsg(null);
    approve.mutate(
      { requestId: row.id, decisionNote: note || undefined },
      { onError: (e) => setErrorMsg(extractErrorMessage(e)) }
    );
  };
  const doReject = () => {
    setErrorMsg(null);
    reject.mutate(
      { requestId: row.id, decisionNote: note || undefined },
      { onError: (e) => setErrorMsg(extractErrorMessage(e)) }
    );
  };

  const isWfh = row.requestType === "wfh";
  return (
    <div
      className={
        "rounded border p-4 " +
        (isWfh ? "border-navy2/40 bg-navy2/5" : "border-line bg-card")
      }
    >
      <button
        onClick={onToggle}
        className="flex w-full items-center justify-between text-left"
      >
        <div className="flex items-center gap-2">
          <TypeBadge requestType={row.requestType} />
          <span className="font-medium text-ink">{row.employeeName}</span>
          <span className="text-sm text-inkSoft">
            {row.leaveType ? `${row.leaveType} · ` : ""}
            {row.startDate} → {row.endDate}
            {row.daysRequested ? ` (${row.daysRequested}d)` : ""}
          </span>
        </div>
        <span className="text-xs text-inkSoft">
          {expanded ? "▲" : "▼"}
        </span>
      </button>

      {expanded ? (
        <div className="mt-3 space-y-3">
          {row.reason ? (
            <p className="text-sm text-inkSoft">
              <span className="font-medium text-ink">Reason:</span> {row.reason}
            </p>
          ) : null}
          <textarea
            placeholder="Optional decision note"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
          />
          {errorMsg ? (
            <div className="rounded border border-clay/40 bg-clay/10 px-3 py-2 text-sm text-clay">
              {errorMsg}
            </div>
          ) : null}
          <div className="flex gap-2">
            <button
              onClick={doApprove}
              disabled={busy}
              className="rounded border border-moss bg-moss px-4 py-2 text-sm font-semibold text-paper transition hover:opacity-90 disabled:opacity-45"
            >
              Approve
            </button>
            <button
              onClick={doReject}
              disabled={busy}
              className="rounded border border-clay px-4 py-2 text-sm font-semibold text-clay transition hover:bg-clay/10 disabled:opacity-45"
            >
              Reject
            </button>
          </div>
          <RequestHistoryPanel
            employeeId={row.employeeId}
            overlapStart={row.startDate}
            overlapEnd={row.endDate}
          />
        </div>
      ) : null}
    </div>
  );
}

export default function ApprovalsPage() {
  const { data, isLoading } = useLeaveQueue();
  const [params] = useSearchParams();
  const deepLinkId = params.get("requestId");
  const [openId, setOpenId] = useState<string | null>(deepLinkId);

  // Auto-expand the deep-linked request once the queue has loaded it.
  useEffect(() => {
    if (deepLinkId && data?.some((r) => r.id === deepLinkId)) {
      setOpenId(deepLinkId);
    }
  }, [deepLinkId, data]);

  return (
    <PageShell title="Approval queue">
      <p className="text-sm text-inkSoft">
        Pending leave & WFH requests awaiting your decision. Refreshes every 10s.
      </p>
      {isLoading ? (
        <p className="text-sm text-inkSoft">Loading…</p>
      ) : !data || data.length === 0 ? (
        <div className="rounded border border-dashed border-line bg-card p-10 text-center">
          <p className="font-serif text-lg font-semibold text-ink">
            Queue is empty 🎉
          </p>
          <p className="mt-1 text-sm text-inkSoft">
            No requests are waiting on you.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {data.map((row) => (
            <QueueRow
              key={row.id}
              row={row}
              expanded={openId === row.id}
              onToggle={() =>
                setOpenId((cur) => (cur === row.id ? null : row.id))
              }
            />
          ))}
        </div>
      )}
    </PageShell>
  );
}
