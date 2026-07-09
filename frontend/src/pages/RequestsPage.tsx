import { useMemo, useState } from "react";
import PageShell from "@/components/PageShell";
import { extractErrorMessage } from "@/lib/api";
import {
  useApplyRequest,
  useLeaveBalances,
  useLeaveCalendar,
  useMyRequests,
  type RequestType,
  type TeamOverlap,
} from "@/api/leaves";

const LEAVE_TYPES = ["casual", "sick", "earned"];

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "approved"
      ? "bg-moss/15 text-moss"
      : status === "rejected"
        ? "bg-clay/15 text-clay"
        : status === "cancelled"
          ? "bg-paper2 text-inkSoft"
          : "bg-ochre/15 text-ochre";
  return (
    <span className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-medium uppercase ${cls}`}>
      {status}
    </span>
  );
}

function TypeBadge({ requestType }: { requestType: string }) {
  const isWfh = requestType === "wfh";
  return (
    <span
      className={
        "rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold uppercase " +
        (isWfh
          ? "bg-navy2/15 text-navy2"
          : "bg-navy/10 text-navy")
      }
    >
      {isWfh ? "WFH" : "Leave"}
    </span>
  );
}

function ApplyForm() {
  const [requestType, setRequestType] = useState<RequestType>("leave");
  const [leaveType, setLeaveType] = useState("casual");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [reason, setReason] = useState("");
  const [overlap, setOverlap] = useState<TeamOverlap[] | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const apply = useApplyRequest();
  const { data: balances } = useLeaveBalances();
  const selectedBalance = useMemo(
    () => balances?.find((b) => b.leaveType === leaveType),
    [balances, leaveType]
  );

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccess(null);
    setOverlap(null);
    apply.mutate(
      {
        requestType,
        leaveType: requestType === "leave" ? leaveType : undefined,
        startDate,
        endDate,
        reason: reason || undefined,
      },
      {
        onSuccess: (data) => {
          setSuccess(
            `Request submitted — ${data.daysRequested} business day(s), status ${data.status}.`
          );
          setOverlap(data.teamOverlap ?? []);
          setStartDate("");
          setEndDate("");
          setReason("");
        },
        onError: (err) => setErrorMsg(extractErrorMessage(err)),
      }
    );
  };

  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-4 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        New request
      </h2>
      <form onSubmit={submit} className="space-y-4">
        <div className="flex gap-2">
          {(["leave", "wfh"] as RequestType[]).map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setRequestType(t)}
              className={
                "rounded px-4 py-2 text-sm font-medium transition " +
                (requestType === t
                  ? "bg-navy text-paper"
                  : "border border-line text-inkSoft hover:bg-paper2")
              }
            >
              {t === "leave" ? "Leave" : "Work From Home"}
            </button>
          ))}
        </div>

        {requestType === "leave" ? (
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-[1px] text-inkSoft">
              Leave type
            </label>
            <select
              value={leaveType}
              onChange={(e) => setLeaveType(e.target.value)}
              className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
            >
              {LEAVE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </option>
              ))}
            </select>
            {selectedBalance ? (
              <p className="mt-1 text-xs text-inkSoft">
                Balance: {selectedBalance.remaining} remaining ·{" "}
                {selectedBalance.used} used · {selectedBalance.pending} pending
                (of {selectedBalance.total})
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-[1px] text-inkSoft">
              Start date
            </label>
            <input
              type="date"
              required
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
            />
          </div>
          <div>
            <label className="mb-1 block font-mono text-[10px] uppercase tracking-[1px] text-inkSoft">
              End date
            </label>
            <input
              type="date"
              required
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block font-mono text-[10px] uppercase tracking-[1px] text-inkSoft">
            Reason (optional)
          </label>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
          />
        </div>

        {errorMsg ? (
          <div className="rounded border border-clay/40 bg-clay/10 px-3 py-2 text-sm text-clay">
            {errorMsg}
          </div>
        ) : null}
        {success ? (
          <div className="rounded border border-moss/40 bg-moss/10 px-3 py-2 text-sm text-moss">
            {success}
          </div>
        ) : null}
        {overlap && overlap.length > 0 ? (
          <div className="rounded border border-ochre/40 bg-ochre/10 px-3 py-2 text-sm text-ochre">
            <p className="font-medium">Heads up — overlapping team requests:</p>
            <ul className="mt-1 list-disc pl-5">
              {overlap.map((o, i) => (
                <li key={i}>
                  {o.employeeName} ({o.requestType}) {o.startDate} → {o.endDate}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <button
          type="submit"
          disabled={apply.isPending}
          className="rounded border border-navy bg-navy px-4 py-2 text-sm font-semibold text-paper transition hover:bg-navy2 disabled:opacity-45"
        >
          {apply.isPending ? "Submitting…" : "Submit request"}
        </button>
      </form>
    </section>
  );
}

function MyRequests() {
  const { data, isLoading } = useMyRequests();
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        My requests
      </h2>
      {isLoading ? (
        <p className="text-sm text-inkSoft">Loading…</p>
      ) : !data || data.length === 0 ? (
        <p className="text-sm text-inkSoft">No requests yet.</p>
      ) : (
        <div className="divide-y divide-line">
          {data.map((r) => (
            <div
              key={r.id}
              className="flex items-center justify-between py-2 text-sm"
            >
              <div className="flex items-center gap-2">
                <TypeBadge requestType={r.requestType} />
                <span className="text-ink">
                  {r.leaveType ? `${r.leaveType} · ` : ""}
                  {r.startDate} → {r.endDate}
                  {r.daysRequested ? ` (${r.daysRequested}d)` : ""}
                </span>
              </div>
              <StatusBadge status={r.status} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function TeamCalendar() {
  const { data, isLoading } = useLeaveCalendar();
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        Team calendar (upcoming)
      </h2>
      {isLoading ? (
        <p className="text-sm text-inkSoft">Loading…</p>
      ) : !data || data.length === 0 ? (
        <p className="text-sm text-inkSoft">Nobody scheduled out.</p>
      ) : (
        <div className="space-y-2">
          {data.map((r) => (
            <div
              key={r.id}
              className="flex items-center justify-between rounded border border-line px-3 py-2 text-sm"
            >
              <div className="flex items-center gap-2">
                <TypeBadge requestType={r.requestType} />
                <span className="text-ink">{r.employeeName}</span>
              </div>
              <span className="text-inkSoft">
                {r.startDate} → {r.endDate}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function RequestsPage() {
  const [tab, setTab] = useState<"apply" | "calendar">("apply");
  return (
    <PageShell title="Leave & WFH">
      <div className="flex gap-2">
        <button
          onClick={() => setTab("apply")}
          className={
            "rounded px-3 py-1.5 text-sm font-medium " +
            (tab === "apply"
              ? "bg-navy text-paper"
              : "border border-line text-inkSoft hover:bg-paper2")
          }
        >
          Apply & history
        </button>
        <button
          onClick={() => setTab("calendar")}
          className={
            "rounded px-3 py-1.5 text-sm font-medium " +
            (tab === "calendar"
              ? "bg-navy text-paper"
              : "border border-line text-inkSoft hover:bg-paper2")
          }
        >
          Team calendar
        </button>
      </div>
      {tab === "apply" ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <ApplyForm />
          <MyRequests />
        </div>
      ) : (
        <TeamCalendar />
      )}
    </PageShell>
  );
}
