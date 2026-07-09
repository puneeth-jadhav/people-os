import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ApiEnvelope } from "@/lib/types";

export interface DocumentRow {
  id: string;
  ownerId: string | null;
  docCategory: "personal" | "policy";
  docType: string;
  title: string;
  version: number;
  changeSummary: string | null;
  requiresAck: boolean;
  visibleRoles: string[] | null;
  createdAt: string | null;
  acknowledged: boolean | null;
}

export interface DocumentSearchResult {
  id: string;
  title: string;
  docType: string;
  docCategory: "personal" | "policy";
  version: number;
  snippet: string | null;
}

export interface UploadDocumentPayload {
  file: File;
  title: string;
  docCategory: "personal" | "policy";
  docType: string;
  ownerId?: string;
  visibleRoles?: string[];
  requiresAck?: boolean;
  changeSummary?: string;
}

export interface ParsedDocument {
  docTypeGuess: string;
  confidence: number;
  extractedFields: {
    aadhaar?: string | null;
    pan?: string | null;
    dateOfBirth?: string | null;
    name?: string | null;
    [key: string]: unknown;
  };
}

// Non-persisting OCR parse of an uploaded file. Any logged-in user can call it.
export async function parseDocument(file: File): Promise<ParsedDocument> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<ApiEnvelope<ParsedDocument>>(
    "/documents/parse",
    form,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return res.data.data;
}

export interface SaveIdNumbersPayload {
  aadhaarNumber?: string | null;
  panNumber?: string | null;
}


// --- queries ---

export function useDocuments(category?: "personal" | "policy") {
  return useQuery({
    queryKey: ["documents", category ?? "all"],
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<DocumentRow[]>>("/documents", {
        params: category ? { category } : undefined,
      });
      return res.data.data;
    },
  });
}

export function useDocumentSearch(q: string) {
  return useQuery({
    queryKey: ["documents", "search", q],
    enabled: q.trim().length > 0,
    queryFn: async () => {
      const res = await api.get<ApiEnvelope<DocumentSearchResult[]>>(
        "/documents/search",
        { params: { q } }
      );
      return res.data.data;
    },
  });
}

// --- mutations / on-demand fetches ---

// Fetch a short-lived signed URL for a document (authorization enforced +
// audited server-side). Never returns a permanent public URL.
export async function fetchDownloadUrl(
  documentId: string
): Promise<{ url: string; expiresIn: number }> {
  const res = await api.get<ApiEnvelope<{ url: string; expiresIn: number }>>(
    `/documents/${documentId}/download`
  );
  return res.data.data;
}

export function useAcknowledge() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (documentId: string) => {
      const res = await api.post<
        ApiEnvelope<{ documentId: string; acknowledged: boolean }>
      >(`/documents/${documentId}/acknowledge`);
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: UploadDocumentPayload) => {
      const form = new FormData();
      form.append("file", payload.file);
      form.append("title", payload.title);
      form.append("doc_category", payload.docCategory);
      form.append("doc_type", payload.docType);
      if (payload.ownerId) form.append("owner_id", payload.ownerId);
      if (payload.visibleRoles && payload.visibleRoles.length > 0) {
        form.append("visible_roles", payload.visibleRoles.join(","));
      }
      if (payload.requiresAck) form.append("requires_ack", "true");
      if (payload.changeSummary) form.append("change_summary", payload.changeSummary);
      const res = await api.post<ApiEnvelope<DocumentRow>>("/documents", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["documents"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

// Download the acknowledgements CSV export (HR only). Triggers a browser download.
export async function downloadAcksCsv(): Promise<void> {
  const res = await api.get("/documents/acks/export", {
    responseType: "blob",
  });
  const blob = new Blob([res.data as BlobPart], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "acknowledgements.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Persist confirmed Aadhaar/PAN numbers onto the current user's own profile.
export function useSaveIdNumbers() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: SaveIdNumbersPayload) => {
      const res = await api.patch<
        ApiEnvelope<{ id: string; aadhaarNumber: string | null; panNumber: string | null }>
      >("/employees/me/id-numbers", payload);
      return res.data.data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["employees"] });
      qc.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

