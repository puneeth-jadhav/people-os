import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  ReactNode,
} from "react";
import { api, setOnAuthFailure } from "@/lib/api";
import { tokenStore } from "@/lib/tokenStore";
import type { LoginResponse, User } from "@/lib/types";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const clearSession = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  // Register hard-logout callback for the axios interceptor.
  useEffect(() => {
    setOnAuthFailure(() => clearSession());
    return () => setOnAuthFailure(null);
  }, [clearSession]);

  // On mount, if a refresh token is persisted, re-hydrate the session:
  // the access token lives in memory only, so it is gone after a reload.
  // The 401 response interceptor will transparently exchange the refresh
  // token for a fresh access token when /auth/me is called.
  useEffect(() => {
    let active = true;
    async function bootstrap() {
      if (!tokenStore.getRefresh()) {
        setLoading(false);
        return;
      }
      try {
        const res = await api.get("/auth/me");
        if (active) setUser(res.data.data as User);
      } catch {
        if (active) clearSession();
      } finally {
        if (active) setLoading(false);
      }
    }
    bootstrap();
    return () => {
      active = false;
    };
  }, [clearSession]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await api.post("/auth/login", { email, password });
    const data = res.data.data as LoginResponse;
    tokenStore.set(data.accessToken, data.refreshToken);
    setUser(data.user);
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = tokenStore.getRefresh();
    try {
      if (refreshToken) {
        await api.post("/auth/logout", { refreshToken });
      }
    } catch {
      // ignore network errors on logout
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const value = useMemo(
    () => ({ user, loading, login, logout }),
    [user, loading, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
