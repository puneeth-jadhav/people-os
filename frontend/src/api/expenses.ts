import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiEnvelope } from "@/lib/types";

export type ExpenseStatus =
  | "submitted"
  | "pending_manager"
  | "pending_finance"
  | "paid"
  | "rejected";

export interface ExpenseRow {
  id: string;
  employeeId: string;
  employeeName: string;
  amount: number | null;
  category: string;
  description: string | null;
  expenseDate: string | null;
  hasReceipt: boolean;
  status: ExpenseStatus;
  approverId: string | null;
  financeApproverId: string | null;
  requiresFinance: boolean;
  submittedAt: string | null;
  resolvedAt: string | null;
}

export interface ParsedFields {
  amount: number | null;
  date: string | null;
  category: string;
  email: string | null;
  name: string | null;
  dateOfJoining: string | null;
  department: string | null;
  designation: string | null;
}

export interface ParsedReceipt {
  docTypeGuess: string;
  confidence: number;
  extractedFields: ParsedFields;
}

export interface UploadReceiptResult {
  receiptPath: string;
  parsed?: ParsedReceipt;
}

export interface CreateExpensePayload {
  amount: number;
  category: string;
  description?: string;
  expenseDate?: string;
  receiptPath?: string;
}

export interface DecisionPayload {
  expenseId: string;
  decisionNote?: string;
}

// --- queries ---

export function useMyExpenses() {
  return useQuery({
    queryKey: ["expenses", "mine"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<ExpenseRow[]>>("/expenses");
      return res.data.data;
    },
  });
}

export function useExpenseQueue() {
  return useQuery({
    queryKey: ["expenses", "queue"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<ExpenseRow[]>>("/expenses/queue");
      return res.data.data;
    },
    refetchInterval: 10_000,
  });
}

export function useFinanceQueue() {
  return useQuery({
    queryKey: ["expenses", "finance-queue"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<ExpenseRow[]>>(
        "/expenses/finance-queue"
      );
      return res.data.data;
    },
    refetchInterval: 10_000,
  });
}

// --- mutations ---

export function useUploadReceipt() {
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      form.append("parse", "true");
      const res = await api.post<ApiEnvelope<UploadReceiptResult>>(
        "/expenses/upload-receipt",
        form,
        { headers: { "Content-Type": "multipart/form-data" } }
      );
      return res.data.data;
    },
  });
}

export function useCreateExpense() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: CreateExpensePayload) => {
      const res = await api.post<ApiEnvelope<ExpenseRow>>(
        "/expenses",
        payload
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["expenses"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useManagerApproveExpense() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ expenseId, decisionNote }: DecisionPayload) => {
      const res = await api.post<ApiEnvelope<ExpenseRow>>(
        `/expenses/${expenseId}/manager-approve`,
        { decisionNote }
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["expenses"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useFinanceApproveExpense() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ expenseId, decisionNote }: DecisionPayload) => {
      const res = await api.post<ApiEnvelope<ExpenseRow>>(
        `/expenses/${expenseId}/finance-approve`,
        { decisionNote }
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["expenses"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useRejectExpense() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ expenseId, decisionNote }: DecisionPayload) => {
      const res = await api.post<ApiEnvelope<ExpenseRow>>(
        `/expenses/${expenseId}/reject`,
        { decisionNote }
      );
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["expenses"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}


// Fetch a short-lived signed URL for a receipt (authorization enforced +
// audited server-side). Never returns a permanent public URL.
export async function fetchReceiptUrl(expenseId: string): Promise<string> {
  const res = await api.get<ApiEnvelope<{ receiptUrl: string }>>(
    `/expenses/${expenseId}/receipt`
  );
  return res.data.data.receiptUrl;
}

// Download the finance CSV export (HR only). Triggers a browser download.
export async function downloadFinanceCsv(): Promise<void> {
  const res = await api.get("/expenses/finance/export", {
    responseType: "blob",
  });
  const blob = new Blob([res.data as BlobPart], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "expenses.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
