import { FormEvent, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { extractErrorMessage } from "@/lib/api";

interface LocationState {
  from?: { pathname?: string };
}

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as LocationState)?.from?.pathname || "/";

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(extractErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-navy px-4">
      <div className="w-[360px] rounded bg-card px-8 py-9 shadow-md">
        <div className="mb-5 flex items-center gap-2.5 font-mono text-[11px] tracking-[1px] text-inkSoft">
          PEOPLEOS · SIGN IN
        </div>
        <h1 className="mb-6 font-serif text-2xl font-semibold text-ink">
          PeopleOS
        </h1>
        <form onSubmit={handleSubmit}>
          <div className="mb-3.5">
            <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-[1px] text-inkSoft">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full rounded border border-line bg-white px-2.5 py-2 text-[13px] text-ink focus:border-navy2"
              autoComplete="username"
            />
          </div>
          <div className="mb-3.5">
            <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-[1px] text-inkSoft">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full rounded border border-line bg-white px-2.5 py-2 text-[13px] text-ink focus:border-navy2"
              autoComplete="current-password"
            />
          </div>
          {error && (
            <div className="mb-3 text-sm text-clay">{error}</div>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded border border-navy bg-navy px-3 py-2.5 text-sm font-semibold text-paper transition hover:bg-navy2 disabled:opacity-45"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="mt-6 text-[13px] text-inkSoft">
          Demo: employee@peopleos.dev / Password123!
        </p>
      </div>
    </div>
  );
}
