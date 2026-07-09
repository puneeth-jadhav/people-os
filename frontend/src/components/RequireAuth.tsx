import { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import type { Role } from "@/lib/types";

const RANK: Record<Role, number> = {
  new_hire: 0,
  employee: 1,
  manager: 2,
  hr_admin: 3,
};

interface RequireAuthProps {
  children: ReactNode;
  minRole?: Role;
}

export function RequireAuth({ children, minRole }: RequireAuthProps) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return <div style={{ padding: 24 }}>Loading…</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (minRole && RANK[user.role] < RANK[minRole]) {
    return <Navigate to="/forbidden" replace />;
  }

  return <>{children}</>;
}
