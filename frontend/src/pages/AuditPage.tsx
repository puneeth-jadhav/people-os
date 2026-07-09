import { useState } from "react";
import PageShell from "@/components/PageShell";
import { extractErrorMessage } from "@/lib/api";
import { downloadAuditCsv, useAuditLog } from "@/api/audit";

const ACTION_FILTERS = [
  "",
  "employee.created",
  "leave.approved",
  "leave.rejected",
  "expense.manager_approved",
  "expense.finance_approved",
  "expense.rejected",
  "document.downloaded",
  "policy.published",
  "policy.acknowledged",
  "data.exported",
];

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString();
}

export default function AuditPage() {
  const [action, setAction] = useState("");
  const { data, isLoading } = useAuditLog({ action: action || undefined });
  const [err, setErr] = useState<string | null>(null);

  return (
    <PageShell title="Audit log">
      <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <label className="text-sm font-semibold text-navy">Action:</label>
            <select
              value={action}
              onChange={(e) => setAction(e.target.value)}
              className="rounded border border-line bg-white px-3 py-1.5 text-sm text-ink focus:border-navy2"
            >
              {ACTION_FILTERS.map((a) => (
                <option key={a} value={a}>
                  {a || "All actions"}
                </option>
              ))}
            </select>
          </div>
          <button
            onClick={() =>
              downloadAuditCsv({ action: action || undefined }).catch((e) =>
                setErr(extractErrorMessage(e))
              )
            }
            className="rounded border border-line px-3 py-1.5 text-sm font-medium text-inkSoft transition hover:bg-paper2"
          >
            Export CSV
          </button>
        </div>
        {err ? (
          <p className="mb-2 text-sm text-clay">{err}</p>
        ) : null}

        {isLoading ? (
          <p className="text-sm text-inkSoft">Loading…</p>
        ) : !data || data.length === 0 ? (
          <p className="text-sm text-inkSoft">No audit entries.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-line font-mono text-xs uppercase tracking-wide text-inkSoft">
                  <th className="py-2 pr-4">Time</th>
                  <th className="py-2 pr-4">Actor</th>
                  <th className="py-2 pr-4">Action</th>
                  <th className="py-2 pr-4">Resource</th>
                </tr>
              </thead>
              <tbody>
                {data.map((r) => (
                  <tr key={r.id} className="border-b border-line">
                    <td className="py-2 pr-4 text-inkSoft">
                      {fmtTime(r.createdAt)}
                    </td>
                    <td className="py-2 pr-4 text-ink">{r.actorName}</td>
                    <td className="py-2 pr-4">
                      <span className="rounded bg-navy/10 px-1.5 py-0.5 font-mono text-xs text-navy">
                        {r.action}
                      </span>
                    </td>
                    <td className="py-2 pr-4 text-inkSoft">
                      {r.resourceType}
                      {r.resourceId ? (
                        <span className="text-inkSoft/60">
                          {" "}
                          #{r.resourceId.slice(0, 8)}
                        </span>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </PageShell>
  );
}
