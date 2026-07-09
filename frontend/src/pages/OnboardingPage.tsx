import { useAuth } from "@/context/AuthContext";
import PageShell from "@/components/PageShell";
import ProgressRing from "@/components/dashboard/ProgressRing";
import {
  useCompleteTask,
  useMyOnboarding,
  type OnboardingTask,
} from "@/api/onboarding";

const STATUS_STYLE: Record<string, string> = {
  done: "bg-moss/15 text-moss",
  in_progress: "bg-navy/10 text-navy",
  unlocked: "bg-ochre/15 text-ochre",
  locked: "bg-paper2 text-inkSoft",
};

const STATUS_LABEL: Record<string, string> = {
  done: "Done",
  in_progress: "In progress",
  unlocked: "Ready",
  locked: "Locked",
};

export default function OnboardingPage() {
  const { user } = useAuth();
  const { data: run, isLoading } = useMyOnboarding();
  const complete = useCompleteTask();

  return (
    <PageShell title="Onboarding">
      {isLoading && <p className="text-sm text-inkSoft">Loading…</p>}

      {!isLoading && !run && (
        <section className="rounded border border-line bg-card p-6 text-sm text-inkSoft shadow-sm">
          You have no active onboarding. If you just joined, check back shortly.
        </section>
      )}

      {run && (
        <section className="rounded border border-line border-t-4 border-t-navy bg-card p-6 shadow-sm">
          <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-start">
            <ProgressRing
              percent={run.progress.percent}
              completed={run.progress.completed}
              total={run.progress.total}
            />
            <div className="flex-1">
              <h2 className="mb-1 text-sm font-mono uppercase tracking-wide text-navy">
                Your onboarding checklist
              </h2>
              {run.status === "completed" && (
                <p className="mb-3 text-sm font-medium text-moss">
                  🎉 Onboarding complete — welcome aboard!
                </p>
              )}
              <ol className="space-y-2">
                {run.tasks.map((t) => (
                  <TaskRow
                    key={t.id}
                    task={t}
                    isMine={t.ownerId === user?.id}
                    busy={complete.isPending}
                    onComplete={() =>
                      complete.mutate({ runId: t.runId, taskId: t.id })
                    }
                  />
                ))}
              </ol>
              {complete.isError && (
                <p className="mt-3 text-sm text-clay">
                  Could not complete task. It may be locked or not yours.
                </p>
              )}
            </div>
          </div>
        </section>
      )}
    </PageShell>
  );
}

function ownerLabel(isMine: boolean): string {
  if (isMine) return "You";
  return "your manager / HR";
}

function TaskRow({
  task,
  isMine,
  busy,
  onComplete,
}: {
  task: OnboardingTask;
  isMine: boolean;
  busy: boolean;
  onComplete: () => void;
}) {
  const canComplete =
    isMine && (task.status === "unlocked" || task.status === "in_progress");

  return (
    <li className="flex items-center justify-between gap-3 rounded bg-paper2 px-4 py-2.5">
      <div className="flex items-center gap-3">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-line text-xs font-semibold text-inkSoft">
          {task.stepIndex + 1}
        </span>
        <div>
          <p className="text-sm font-medium text-ink">{task.title}</p>
          <p className="text-xs text-inkSoft">
            {task.status === "done"
              ? "Completed"
              : task.status === "locked"
                ? "Waiting on earlier steps"
                : `Waiting on ${ownerLabel(isMine)}`}
            {task.delayed && task.status !== "done" && (
              <span className="ml-2 rounded-full bg-clay/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-clay">Delayed</span>
            )}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span
          className={
            "rounded-full px-2.5 py-0.5 text-xs font-medium " +
            (STATUS_STYLE[task.status] ?? "bg-paper2 text-inkSoft")
          }
        >
          {STATUS_LABEL[task.status] ?? task.status}
        </span>
        {canComplete && (
          <button
            onClick={onComplete}
            disabled={busy}
            className="rounded bg-navy px-3 py-1 text-xs font-medium text-paper transition hover:bg-navy2 disabled:opacity-50"
          >
            Complete
          </button>
        )}
      </div>
    </li>
  );
}
