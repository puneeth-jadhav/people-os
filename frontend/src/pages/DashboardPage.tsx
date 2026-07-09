import { useDashboard, type DashboardData } from "@/api/dashboard";
import PageShell from "@/components/PageShell";
import HeroZone from "@/components/dashboard/HeroZone";
import NeedsAttention from "@/components/dashboard/NeedsAttention";
import WaitingOnOthers from "@/components/dashboard/WaitingOnOthers";
import UpcomingZone from "@/components/dashboard/UpcomingZone";
import RecentChanges from "@/components/dashboard/RecentChanges";
import QuickActions from "@/components/dashboard/QuickActions";
import LeaveBalances from "@/components/dashboard/LeaveBalances";
import TeamAvailability from "@/components/dashboard/TeamAvailability";
import OnboardingChecklist from "@/components/dashboard/OnboardingChecklist";
import { OnboardingRuns, AckStatus } from "@/components/dashboard/HrPanels";

function hasItems(arr?: unknown[]): boolean {
  return Array.isArray(arr) && arr.length > 0;
}

function AllCaughtUp() {
  return (
    <div className="rounded border border-dashed border-line bg-card p-10 text-center">
      <p className="font-serif text-lg font-semibold text-ink">All caught up 🎉</p>
      <p className="mt-1 text-sm text-inkSoft">
        Nothing needs your attention right now.
      </p>
    </div>
  );
}

function EmployeeDashboard({ data }: { data: DashboardData }) {
  const actionable =
    hasItems(data.needsAttention) ||
    hasItems(data.waitingOnOthers) ||
    hasItems(data.upcoming);
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        {data.leaveBalances && data.leaveBalances.length > 0 ? (
          <LeaveBalances balances={data.leaveBalances} />
        ) : null}
        {hasItems(data.needsAttention) ? (
          <NeedsAttention items={data.needsAttention!} />
        ) : null}
        {hasItems(data.upcoming) ? (
          <UpcomingZone items={data.upcoming!} />
        ) : null}
        {!actionable ? <AllCaughtUp /> : null}
      </div>
      <div className="space-y-4">
        {hasItems(data.waitingOnOthers) ? (
          <WaitingOnOthers items={data.waitingOnOthers!} />
        ) : null}
        {hasItems(data.quickActions) ? (
          <QuickActions actions={data.quickActions!} />
        ) : null}
      </div>
    </div>
  );
}

function ManagerDashboard({ data }: { data: DashboardData }) {
  const actionable =
    hasItems(data.needsAttention) || hasItems(data.teamAvailability);
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        {hasItems(data.needsAttention) ? (
          <NeedsAttention
            items={data.needsAttention!}
            title="Pending approvals"
          />
        ) : null}
        {!actionable ? <AllCaughtUp /> : null}
      </div>
      <div className="space-y-4">
        <TeamAvailability items={data.teamAvailability ?? []} />
        {hasItems(data.recentChanges) ? (
          <RecentChanges items={data.recentChanges!} />
        ) : null}
        {hasItems(data.quickActions) ? (
          <QuickActions actions={data.quickActions!} />
        ) : null}
      </div>
    </div>
  );
}

function NewHireDashboard({ data }: { data: DashboardData }) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        {data.onboarding ? (
          <OnboardingChecklist onboarding={data.onboarding} />
        ) : null}
        {hasItems(data.needsAttention) ? (
          <NeedsAttention
            items={data.needsAttention!}
            title="Your next steps"
          />
        ) : null}
      </div>
      <div className="space-y-4">
        {hasItems(data.waitingOnOthers) ? (
          <WaitingOnOthers items={data.waitingOnOthers!} />
        ) : null}
        {hasItems(data.upcoming) ? (
          <UpcomingZone items={data.upcoming!} />
        ) : null}
        {hasItems(data.quickActions) ? (
          <QuickActions actions={data.quickActions!} />
        ) : null}
      </div>
    </div>
  );
}

function HrDashboard({ data }: { data: DashboardData }) {
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        {hasItems(data.needsAttention) ? (
          <NeedsAttention
            items={data.needsAttention!}
            title="Compliance & finance queue"
          />
        ) : (
          <AllCaughtUp />
        )}
        <AckStatus items={data.ackStatus ?? []} />
      </div>
      <div className="space-y-4">
        <OnboardingRuns runs={data.onboardingRuns ?? []} />
        {hasItems(data.recentChanges) ? (
          <RecentChanges items={data.recentChanges!} />
        ) : null}
        {hasItems(data.quickActions) ? (
          <QuickActions actions={data.quickActions!} />
        ) : null}
      </div>
    </div>
  );
}

function DashboardBody({ data }: { data: DashboardData }) {
  switch (data.experience) {
    case "new_hire":
      return <NewHireDashboard data={data} />;
    case "manager":
      return <ManagerDashboard data={data} />;
    case "hr_admin":
      return <HrDashboard data={data} />;
    default:
      return <EmployeeDashboard data={data} />;
  }
}

export default function DashboardPage() {
  const { data, isLoading, isError } = useDashboard();

  return (
    <PageShell title="Dashboard">
      {isLoading ? (
        <p className="text-sm text-inkSoft">Loading your dashboard…</p>
      ) : isError || !data ? (
        <div className="rounded border border-clay/40 bg-clay/10 p-6 text-sm text-clay">
          Could not load your dashboard. Please try again.
        </div>
      ) : (
        <div className="space-y-4">
          <HeroZone hero={data.hero} />
          <DashboardBody data={data} />
        </div>
      )}
    </PageShell>
  );
}
