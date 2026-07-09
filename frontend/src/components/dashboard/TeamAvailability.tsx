import type { TeamAvailabilityItem } from "@/api/dashboard";

export default function TeamAvailability({
  items,
}: {
  items: TeamAvailabilityItem[];
}) {
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        Team availability
      </h2>
      {items.length === 0 ? (
        <p className="text-sm text-inkSoft">
          Everyone on your team is available.
        </p>
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li
              key={item.id}
              className="flex items-center justify-between rounded bg-paper px-4 py-2.5"
            >
              <div className="flex items-center gap-2">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${
                    item.status === "today" ? "bg-clay" : "bg-ochre"
                  }`}
                />
                <span className="text-sm font-medium text-ink">
                  {item.employee}
                </span>
                <span className="rounded bg-paper2 px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase text-inkSoft">
                  {item.kind}
                </span>
              </div>
              <span className="text-xs text-inkSoft">
                {item.status === "today"
                  ? "Away today"
                  : `${item.startDate} → ${item.endDate}`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
