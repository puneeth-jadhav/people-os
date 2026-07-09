import type { QuickAction } from "@/api/dashboard";

export default function QuickActions({ actions }: { actions: QuickAction[] }) {
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        Quick actions
      </h2>
      <div className="flex flex-wrap gap-2">
        {actions.map((a) => (
          <a
            key={a.label}
            href={a.link}
            className="rounded bg-navy px-3 py-2 text-sm font-medium text-paper transition hover:bg-navy2"
          >
            {a.label}
          </a>
        ))}
      </div>
    </section>
  );
}
