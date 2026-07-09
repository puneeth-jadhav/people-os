import type { ActionItem } from "@/api/dashboard";

export default function UpcomingZone({ items }: { items: ActionItem[] }) {
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        Upcoming
      </h2>
      <ul className="space-y-2">
        {items.map((item) => (
          <li key={item.id} className="flex items-start gap-3 px-1 py-2">
            <span className="mt-1 h-2 w-2 flex-shrink-0 rounded-full bg-navy2" />
            <div>
              <p className="text-sm font-medium text-ink">{item.title}</p>
              {item.subtitle ? (
                <p className="mt-0.5 text-xs text-inkSoft">{item.subtitle}</p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
