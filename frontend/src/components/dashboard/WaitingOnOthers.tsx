import type { ActionItem } from "@/api/dashboard";

export default function WaitingOnOthers({ items }: { items: ActionItem[] }) {
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        Waiting on others
      </h2>
      <ul className="space-y-2">
        {items.map((item) => (
          <li
            key={item.id}
            className="flex items-center justify-between rounded bg-paper px-4 py-3"
          >
            <div>
              <p className="text-sm font-medium text-ink">{item.title}</p>
              {item.subtitle ? (
                <p className="mt-0.5 text-xs text-inkSoft">{item.subtitle}</p>
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
                {item.ageDays} days
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
