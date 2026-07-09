import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiEnvelope } from "@/lib/types";

export interface EmployeeRow {
  id: string;
  name: string;
  email: string;
  role: string;
  departmentId: string | null;
  managerId: string | null;
  designation: string | null;
  status: string;
  employmentType?: string;
  joinDate?: string | null;
}

export interface CreatedEmployee extends EmployeeRow {
  onboardingRunId: string;
  taskCount: number;
}

export interface CreateEmployeePayload {
  name: string;
  email: string;
  role?: string;
  departmentId?: string;
  managerId?: string;
  designation?: string;
  joinDate?: string;
  employmentType?: string;
}

export function useEmployees(enabled = true) {
  return useQuery({
    queryKey: ["employees", "list"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<EmployeeRow[]>>("/employees");
      return res.data.data;
    },
    enabled,
  });
}

export function useCreateEmployee() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateEmployeePayload) => {
      const res = await api.post<ApiEnvelope<CreatedEmployee>>(
        "/employees",
        payload
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      qc.invalidateQueries({ queryKey: ["onboarding"] });
    },
  });
}
