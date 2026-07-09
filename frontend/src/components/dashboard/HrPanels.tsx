import type { OnboardingRunItem, AckStatusItem } from "@/api/dashboard";

export function OnboardingRuns({ runs }: { runs: OnboardingRunItem[] }) {
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        Active onboarding ({runs.length})
      </h2>
      {runs.length === 0 ? (
        <p className="text-sm text-inkSoft">No onboarding runs in progress.</p>
      ) : (
        <ul className="space-y-3">
          {runs.map((r) => (
            <li key={r.id}>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm font-medium text-ink">
                  {r.employee}
                </span>
                <span className="text-xs text-inkSoft">
                  {r.completed}/{r.total} · {r.percent}%
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-paper2">
                <div
                  className="h-2 rounded-full bg-navy"
                  style={{ width: `${r.percent}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function AckStatus({ items }: { items: AckStatusItem[] }) {
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        Policy acknowledgements
      </h2>
      {items.length === 0 ? (
        <p className="text-sm text-inkSoft">No policies require acknowledgement.</p>
      ) : (
        <ul className="space-y-3">
          {items.map((a) => (
            <li key={a.id}>
              <div className="mb-1 flex items-center justify-between">
                <span className="text-sm font-medium text-ink">
                  {a.title}{" "}
                  <span className="text-xs text-inkSoft">v{a.version}</span>
                </span>
                <span className="text-xs text-inkSoft">
                  {a.acked}/{a.total}
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-paper2">
                <div
                  className={`h-2 rounded-full ${
                    a.percent >= 100 ? "bg-moss" : "bg-ochre"
                  }`}
                  style={{ width: `${a.percent}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
