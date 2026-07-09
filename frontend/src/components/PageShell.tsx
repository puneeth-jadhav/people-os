import { Link, useLocation } from "react-router-dom";
import { ReactNode } from "react";
import { useAuth } from "@/context/AuthContext";
import NotificationBell from "@/components/NotificationBell";

const NAV = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/requests", label: "My Requests" },
  { to: "/expenses", label: "Expenses" },
  { to: "/onboarding", label: "Onboarding" },
  { to: "/documents", label: "Documents" },
  { to: "/approvals", label: "Approvals", minRole: "manager" as const },
  { to: "/people", label: "People", minRole: "hr_admin" as const },
  { to: "/audit", label: "Audit", minRole: "hr_admin" as const },
];

const RANK: Record<string, number> = {
  employee: 1,
  new_hire: 1,
  manager: 2,
  hr_admin: 3,
};

export default function PageShell({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const { user, logout } = useAuth();
  const loc = useLocation();
  const rank = RANK[user?.role ?? "employee"] ?? 1;

  return (
    <div className="grid min-h-screen grid-cols-[220px_1fr] bg-paper">
      <aside className="sticky top-0 flex h-screen flex-col bg-navy py-6 text-paper">
        <div className="mb-4 border-b border-white/15 px-5 pb-5">
          <div className="font-serif text-xl font-semibold tracking-tight">
            PeopleOS
          </div>
          <div className="mt-0.5 font-mono text-[10px] tracking-[1.5px] text-[#B9C2D8]">
            HR OPERATING SYSTEM
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto">
          {NAV.filter(
            (n) => !n.minRole || rank >= RANK[n.minRole]
          ).map((n) => {
            const active = loc.pathname === n.to;
            return (
              <Link
                key={n.to}
                to={n.to}
                className={
                  "flex items-center gap-2.5 border-l-[3px] px-5 py-2.5 text-[13px] tracking-[0.3px] transition " +
                  (active
                    ? "border-clay bg-paper font-semibold text-ink"
                    : "border-transparent text-[#C7CEDE] hover:bg-white/[0.07] hover:text-white")
                }
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="mt-auto space-y-3 border-t border-white/15 px-5 pt-4">
          <div className="flex items-center gap-3">
            <NotificationBell />
            <span className="truncate font-mono text-[10px] tracking-[0.5px] text-[#B9C2D8]">
              {user?.name}
            </span>
          </div>
          <button
            onClick={() => logout()}
            className="w-full rounded border border-white/25 px-3 py-1.5 text-xs font-semibold text-[#C7CEDE] transition hover:bg-white/[0.07] hover:text-white"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="mx-auto w-full max-w-5xl space-y-6 px-8 py-7 pb-24">
        <div className="rounded border-l-4 border-clay bg-navy px-6 py-5 shadow-sm">
          <p className="font-mono text-[10px] uppercase tracking-[1.5px] text-[#B9C2D8]">
            PeopleOS
          </p>
          <h1 className="mt-0.5 font-serif text-2xl font-semibold text-paper">
            {title}
          </h1>
        </div>
        {children}
      </main>
    </div>
  );
}
