import axios, {
  AxiosError,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";
import { tokenStore } from "./tokenStore";

const BASE_URL = `${import.meta.env.VITE_API_URL || "http://localhost:8000"}/api/v1`;

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach access token on every request.
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStore.getAccess();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// --- Refresh handling (single-flight, prevents loops) ---
let isRefreshing = false;
let pendingQueue: Array<(token: string | null) => void> = [];

function flushQueue(token: string | null) {
  pendingQueue.forEach((cb) => cb(token));
  pendingQueue = [];
}

// Callback the AuthContext registers so a hard logout can clear React state.
let onAuthFailure: (() => void) | null = null;
export function setOnAuthFailure(cb: (() => void) | null) {
  onAuthFailure = cb;
}

async function requestNewAccessToken(): Promise<string | null> {
  const refreshToken = tokenStore.getRefresh();
  if (!refreshToken) return null;
  try {
    // Bare axios call — must NOT go through the interceptor (avoids loop).
    const res = await axios.post(`${BASE_URL}/auth/refresh`, { refreshToken });
    const newAccess: string = res.data?.data?.accessToken;
    if (newAccess) {
      tokenStore.setAccess(newAccess);
      return newAccess;
    }
    return null;
  } catch {
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as AxiosRequestConfig & {
      _retry?: boolean;
      url?: string;
    };
    const status = error.response?.status;
    const isAuthEndpoint =
      original?.url?.includes("/auth/login") ||
      original?.url?.includes("/auth/refresh");

    if (status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true;

      if (isRefreshing) {
        // Queue until the in-flight refresh resolves.
        return new Promise((resolve, reject) => {
          pendingQueue.push((token) => {
            if (token) {
              original.headers = original.headers || {};
              (original.headers as Record<string, string>).Authorization =
                `Bearer ${token}`;
              resolve(api(original));
            } else {
              reject(error);
            }
          });
        });
      }

      isRefreshing = true;
      const newToken = await requestNewAccessToken();
      isRefreshing = false;
      flushQueue(newToken);

      if (newToken) {
        original.headers = original.headers || {};
        (original.headers as Record<string, string>).Authorization =
          `Bearer ${newToken}`;
        return api(original);
      }

      // Refresh failed -> hard logout.
      tokenStore.clear();
      if (onAuthFailure) onAuthFailure();
    }

    return Promise.reject(error);
  }
);

export function extractErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const body = err.response?.data as
      | { error?: { message?: string } }
      | undefined;
    return body?.error?.message || err.message || "Request failed";
  }
  return "Unexpected error";
}
