import type { DashboardHero } from "@/api/dashboard";

export default function HeroZone({ hero }: { hero: DashboardHero }) {
  return (
    <section className="rounded bg-navy px-6 py-7 text-paper shadow-sm">
      <p className="font-mono text-[10px] uppercase tracking-[1.5px] text-[#B9C2D8]">
        {hero.greeting}
      </p>
      <h1 className="mt-1 font-serif text-2xl font-semibold tracking-tight">
        {hero.headline}
      </h1>
      {hero.subtext ? (
        <p className="mt-2 text-sm text-[#DFE2D8]">{hero.subtext}</p>
      ) : null}
    </section>
  );
}
