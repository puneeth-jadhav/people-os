import type { LeaveBalance } from "@/api/dashboard";

export default function LeaveBalances({
  balances,
}: {
  balances: LeaveBalance[];
}) {
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        Leave balance
      </h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {balances.map((b) => {
          const pct =
            b.total > 0
              ? Math.max(0, Math.min(100, (b.remaining / b.total) * 100))
              : 0;
          return (
            <div
              key={b.leaveType}
              className="rounded bg-paper px-4 py-3"
            >
              <p className="font-mono text-[10px] font-medium uppercase tracking-[1px] text-inkSoft">
                {b.leaveType}
              </p>
              <p className="mt-1 font-serif text-2xl font-semibold text-ink">
                {b.remaining}
                <span className="text-sm font-normal text-inkSoft">
                  {" "}
                  / {b.total}
                </span>
              </p>
              <div className="mt-2 h-1.5 w-full rounded-full bg-paper2">
                <div
                  className="h-1.5 rounded-full bg-moss"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="mt-1 text-[11px] text-inkSoft">
                {b.used} used · {b.pending} pending
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}
