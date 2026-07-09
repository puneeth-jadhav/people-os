import { FormEvent, useState } from "react";
import PageShell from "@/components/PageShell";
import {
  useCreateEmployee,
  useEmployees,
  type CreatedEmployee,
} from "@/api/employees";
import { useOnboardingRuns } from "@/api/onboarding";

export default function PeoplePage() {
  const { data: employees } = useEmployees();
  const { data: runs } = useOnboardingRuns();
  const create = useCreateEmployee();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("employee");
  const [managerId, setManagerId] = useState("");
  const [designation, setDesignation] = useState("");
  const [joinDate, setJoinDate] = useState("");
  const [created, setCreated] = useState<CreatedEmployee | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const managers = (employees ?? []).filter(
    (e) => e.role === "manager" || e.role === "hr_admin"
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setErrorMsg(null);
    setCreated(null);
    try {
      const result = await create.mutateAsync({
        name,
        email,
        role,
        managerId: managerId || undefined,
        designation: designation || undefined,
        joinDate: joinDate || undefined,
      });
      setCreated(result);
      setName("");
      setEmail("");
      setDesignation("");
      setJoinDate("");
      setManagerId("");
    } catch (err: any) {
      setErrorMsg(
        err?.response?.data?.error?.message ?? "Could not create employee"
      );
    }
  }

  return (
    <PageShell title="People">
      <section className="rounded border border-line border-t-4 border-t-navy bg-card p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-mono uppercase tracking-wide text-navy">
          Add employee
        </h2>
        <form
          onSubmit={onSubmit}
          className="grid grid-cols-1 gap-4 sm:grid-cols-2"
        >
          <Field label="Name">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2 focus:outline-none"
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2 focus:outline-none"
            />
          </Field>
          <Field label="Role">
            <select
              value={role}
              onChange={(e) => setRole(e.target.value)}
              className="rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2 focus:outline-none"
            >
              <option value="employee">Employee</option>
              <option value="manager">Manager</option>
              <option value="hr_admin">HR Admin</option>
            </select>
          </Field>
          <Field label="Manager (optional)">
            <select
              value={managerId}
              onChange={(e) => setManagerId(e.target.value)}
              className="rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2 focus:outline-none"
            >
              <option value="">— none —</option>
              {managers.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Designation (optional)">
            <input
              value={designation}
              onChange={(e) => setDesignation(e.target.value)}
              className="rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2 focus:outline-none"
            />
          </Field>
          <Field label="Join date (optional)">
            <input
              type="date"
              value={joinDate}
              onChange={(e) => setJoinDate(e.target.value)}
              className="rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2 focus:outline-none"
            />
          </Field>
          <div className="sm:col-span-2">
            <button
              type="submit"
              disabled={create.isPending}
              className="rounded bg-navy px-4 py-2 text-sm font-medium text-paper transition hover:bg-navy2 disabled:opacity-50"
            >
              {create.isPending ? "Creating…" : "Add employee"}
            </button>
          </div>
        </form>

        {created && (
          <p className="mt-4 rounded border border-moss/40 bg-moss/10 px-4 py-3 text-sm text-moss">
            Created <strong>{created.name}</strong>. Onboarding auto-started with{" "}
            {created.taskCount} task{created.taskCount === 1 ? "" : "s"}.
            Temporary password: <code>Welcome@123</code>.
          </p>
        )}
        {errorMsg && (
          <p className="mt-4 rounded border border-clay/40 bg-clay/10 px-4 py-3 text-sm text-clay">
            {errorMsg}
          </p>
        )}
      </section>

      <section className="rounded border border-line border-t-4 border-t-navy bg-card p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-mono uppercase tracking-wide text-navy">
          Onboarding pipeline
        </h2>
        {(runs ?? []).length === 0 && (
          <p className="text-sm text-inkSoft">No onboarding in progress.</p>
        )}
        <div className="space-y-4">
          {(runs ?? []).map((run) => (
            <div
              key={run.id}
              className="rounded border border-line p-4"
            >
              <div className="mb-2 flex items-center justify-between">
                <p className="text-sm font-semibold text-ink">
                  {run.employeeName}
                </p>
                <span className="text-xs text-inkSoft">
                  {run.progress.completed}/{run.progress.total} done (
                  {run.progress.percent}%)
                </span>
              </div>
              <div className="mb-3 h-2 w-full overflow-hidden rounded-full bg-paper2">
                <div
                  className="h-full rounded-full bg-navy transition-all"
                  style={{ width: `${run.progress.percent}%` }}
                />
              </div>
              <ul className="space-y-1">
                {run.tasks.map((t) => (
                  <li
                    key={t.id}
                    className="flex items-center justify-between text-xs"
                  >
                    <span className="text-inkSoft">
                      {t.stepIndex + 1}. {t.title}
                    </span>
                    <span className="flex items-center gap-2">
                      {t.delayed && t.status !== "done" && (
                        <span className="rounded-full bg-clay/15 px-2 py-0.5 text-[10px] font-semibold uppercase text-clay">
                          Delayed
                        </span>
                      )}
                      <span className="text-inkSoft">{t.status}</span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </PageShell>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="font-medium text-inkSoft">{label}</span>
      {children}
    </label>
  );
}
