import type { ActionItem } from "@/api/dashboard";

interface Props {
  items: ActionItem[];
  title?: string;
}

const KIND_ACCENT: Record<string, string> = {
  policy_ack: "border-l-ochre",
  rejected_leave: "border-l-clay",
  rejected_expense: "border-l-clay",
  approve_leave: "border-l-navy2",
  approve_expense: "border-l-navy2",
  finance_approval: "border-l-moss",
  onboarding_delay: "border-l-clay",
  onboarding_action: "border-l-navy2",
};

export default function NeedsAttention({
  items,
  title = "Needs your attention",
}: Props) {
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
          {title}
        </h2>
        <span className="rounded-full bg-clay/15 px-2 py-0.5 font-mono text-xs font-semibold text-clay">
          {items.length}
        </span>
      </div>
      <ul className="space-y-2">
        {items.map((item) => (
          <li
            key={item.id}
            className={`rounded border-l-4 bg-paper px-4 py-3 ${
              KIND_ACCENT[item.kind] ?? "border-l-line"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-ink">
                  {item.title}
                </p>
                {item.subtitle ? (
                  <p className="mt-0.5 text-xs text-inkSoft">
                    {item.subtitle}
                  </p>
                ) : null}
                {item.contextHint ? (
                  <p className="mt-1 inline-block rounded bg-navy2/10 px-2 py-0.5 text-[11px] font-medium text-navy2">
                    {item.contextHint}
                  </p>
                ) : null}
              </div>
              {typeof item.ageDays === "number" ? (
                <span
                  className={
                    "whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium " +
                    (item.ageDays >= 3
                      ? "bg-clay/15 text-clay"
                      : item.ageDays >= 1
                        ? "bg-ochre/15 text-ochre"
                        : "text-inkSoft")
                  }
                >
                  {item.ageDays}d
                </span>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
