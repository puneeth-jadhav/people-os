// Access token lives in memory only (cleared on full page reload — the session
// is re-hydrated from the refresh token, which is persisted in localStorage).
const REFRESH_KEY = "peopleos.refreshToken";

let accessToken: string | null = null;

export const tokenStore = {
  getAccess(): string | null {
    return accessToken;
  },
  getRefresh(): string | null {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    accessToken = access;
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  setAccess(access: string) {
    accessToken = access;
  },
  clear() {
    accessToken = null;
    localStorage.removeItem(REFRESH_KEY);
  },
};
