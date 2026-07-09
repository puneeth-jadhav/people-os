import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "@/components/RequireAuth";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import ForbiddenPage from "@/pages/ForbiddenPage";
import RequestsPage from "@/pages/RequestsPage";
import ExpensesPage from "@/pages/ExpensesPage";
import ApprovalsPage from "@/pages/ApprovalsPage";
import OnboardingPage from "@/pages/OnboardingPage";
import PeoplePage from "@/pages/PeoplePage";
import DocumentsPage from "@/pages/DocumentsPage";
import AuditPage from "@/pages/AuditPage";

/**
 * PeopleOS route table.
 *
 * - /login is public.
 * - Everything else is wrapped by <RequireAuth>, which redirects
 *   unauthenticated users to /login (preserving the intended path).
 * - /forbidden is shown when a user lacks the required role for a route.
 */
export default function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forbidden" element={<ForbiddenPage />} />

      <Route
        path="/dashboard"
        element={
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        }
      />

      <Route
        path="/requests"
        element={
          <RequireAuth>
            <RequestsPage />
          </RequireAuth>
        }
      />

      <Route
        path="/expenses"
        element={
          <RequireAuth>
            <ExpensesPage />
          </RequireAuth>
        }
      />

      <Route
        path="/onboarding"
        element={
          <RequireAuth>
            <OnboardingPage />
          </RequireAuth>
        }
      />

      <Route
        path="/documents"
        element={
          <RequireAuth>
            <DocumentsPage />
          </RequireAuth>
        }
      />

      <Route
        path="/approvals"
        element={
          <RequireAuth minRole="manager">
            <ApprovalsPage />
          </RequireAuth>
        }
      />

      <Route
        path="/people"
        element={
          <RequireAuth minRole="hr_admin">
            <PeoplePage />
          </RequireAuth>
        }
      />

      <Route
        path="/audit"
        element={
          <RequireAuth minRole="hr_admin">
            <AuditPage />
          </RequireAuth>
        }
      />

      {/* Authenticated landing → role-shaped dashboard. */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* Unknown routes fall back to the dashboard (or /login if signed out). */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
