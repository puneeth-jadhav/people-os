import { Link } from "react-router-dom";
import type { OnboardingProgress } from "@/api/dashboard";
import ProgressRing from "./ProgressRing";

const STATUS_STYLE: Record<string, string> = {
  done: "bg-moss/15 text-moss",
  in_progress: "bg-navy2/15 text-navy2",
  unlocked: "bg-ochre/15 text-ochre",
  locked: "bg-paper2 text-inkSoft",
};

const STATUS_LABEL: Record<string, string> = {
  done: "Done",
  in_progress: "In progress",
  unlocked: "Ready",
  locked: "Locked",
};

export default function OnboardingChecklist({
  onboarding,
}: {
  onboarding: OnboardingProgress;
}) {
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
        <ProgressRing
          percent={onboarding.percent}
          completed={onboarding.completed}
          total={onboarding.total}
        />
        <div className="flex-1">
          <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
            Your onboarding checklist
          </h2>
          <ol className="space-y-2">
            {(onboarding.tasks ?? []).map((t, i) => (
              <li
                key={t.id}
                className="flex items-center justify-between rounded bg-paper px-4 py-2.5"
              >
                <div className="flex items-center gap-3">
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-paper2 font-mono text-xs font-semibold text-inkSoft">
                    {i + 1}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-ink">
                      {t.title}
                    </p>
                    {!t.isMine && t.owner ? (
                      <p className="text-[11px] text-inkSoft">
                        Owner: {t.owner}
                      </p>
                    ) : null}
                  </div>
                </div>
                <span
                  className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold ${
                    STATUS_STYLE[t.status] ?? "bg-paper2 text-inkSoft"
                  }`}
                >
                  {STATUS_LABEL[t.status] ?? t.status}
                </span>
              </li>
            ))}
          </ol>
          <Link
            to="/onboarding"
            className="mt-3 inline-block text-sm font-medium text-navy2 hover:underline"
          >
            Go to onboarding →
          </Link>
        </div>
      </div>
    </section>
  );
}
