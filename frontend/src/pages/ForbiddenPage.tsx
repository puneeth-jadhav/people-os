import { Link } from "react-router-dom";

export default function ForbiddenPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-paper px-6 text-center">
      <h1 className="font-serif text-3xl font-semibold text-ink">
        403 — Forbidden
      </h1>
      <p className="text-sm text-inkSoft">
        You do not have permission to view this page.
      </p>
      <Link
        to="/"
        className="mt-2 rounded border border-navy bg-navy px-4 py-2 text-sm font-semibold text-paper transition hover:bg-navy2"
      >
        Back to dashboard
      </Link>
    </div>
  );
}
