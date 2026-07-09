import { useState } from "react";
import PageShell from "@/components/PageShell";
import { extractErrorMessage } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import {
  useCreateExpense,
  useMyExpenses,
  useUploadReceipt,
  useExpenseQueue,
  useFinanceQueue,
  useManagerApproveExpense,
  useFinanceApproveExpense,
  useRejectExpense,
  fetchReceiptUrl,
  downloadFinanceCsv,
  type ExpenseRow,
  type ExpenseStatus,
} from "@/api/expenses";

const CATEGORIES = ["Travel", "Lodging", "Meals", "Other"];
const FINANCE_THRESHOLD = 10000;

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "paid"
      ? "bg-moss/15 text-moss"
      : status === "rejected"
        ? "bg-clay/15 text-clay"
        : status === "pending_finance"
          ? "bg-navy/10 text-navy"
          : "bg-ochre/15 text-ochre";
  const label = status.replace("_", " ");
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}

// Visual timeline: submitted -> pending_manager -> [pending_finance] -> paid.
// The finance step is only shown when the expense actually required finance.
function StatusTimeline({ row }: { row: ExpenseRow }) {
  if (row.status === "rejected") {
    return (
      <div className="mt-1 text-xs font-medium text-clay">
        Rejected — not paid
      </div>
    );
  }
  const showFinance = row.requiresFinance;
  const steps: { key: string; label: string }[] = [
    { key: "pending_manager", label: "Submitted" },
    { key: "manager", label: "Manager approved" },
  ];
  if (showFinance) steps.push({ key: "pending_finance", label: "Finance" });
  steps.push({ key: "paid", label: "Paid" });

  const order: ExpenseStatus[] = showFinance
    ? ["pending_manager", "pending_finance", "paid"]
    : ["pending_manager", "paid"];
  const reachedIdx = order.indexOf(row.status);

  // Map each timeline node to a completion state.
  const status: string = row.status;
  const completed = (key: string): boolean => {
    if (status === "paid") return true;
    if (key === "pending_manager") return reachedIdx >= 0;
    if (key === "manager") return status === "pending_finance";
    // pending_finance node is only "completed" once fully paid, handled above.
    return false;
  };

  return (
    <div className="mt-2 flex items-center gap-1">
      {steps.map((s, i) => (
        <div key={s.key} className="flex items-center gap-1">
          <span
            className={`h-2 w-2 rounded-full ${
              completed(s.key) ? "bg-moss" : "bg-line"
            }`}
          />
          <span
            className={`text-[10px] ${
              completed(s.key) ? "text-moss" : "text-inkSoft"
            }`}
          >
            {s.label}
          </span>
          {i < steps.length - 1 ? (
            <span className="mx-0.5 text-inkSoft">›</span>
          ) : null}
        </div>
      ))}
    </div>
  );
}

function ReceiptLink({ expenseId }: { expenseId: string }) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const open = async () => {
    setErr(null);
    setLoading(true);
    try {
      const url = await fetchReceiptUrl(expenseId);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (e) {
      setErr(extractErrorMessage(e));
    } finally {
      setLoading(false);
    }
  };
  return (
    <span>
      <button
        type="button"
        onClick={open}
        disabled={loading}
        className="text-xs font-medium text-navy underline hover:text-navy2 disabled:opacity-50"
      >
        {loading ? "Opening…" : "View receipt"}
      </button>
      {err ? <span className="ml-2 text-xs text-clay">{err}</span> : null}
    </span>
  );
}

function FieldLabel({
  children,
  autoFilled,
}: {
  children: React.ReactNode;
  autoFilled?: boolean;
}) {
  return (
    <label className="mb-1 flex items-center gap-2 text-xs font-medium text-inkSoft">
      {children}
      {autoFilled ? (
        <span className="rounded-full bg-ochre/15 px-1.5 py-0.5 text-[10px] font-semibold text-ochre">
          auto-filled
        </span>
      ) : null}
    </label>
  );
}

function ExpenseForm() {
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState("Travel");
  const [description, setDescription] = useState("");
  const [expenseDate, setExpenseDate] = useState("");
  const [receiptPath, setReceiptPath] = useState<string | null>(null);
  const [autoFillNote, setAutoFillNote] = useState<string | null>(null);
  const [filled, setFilled] = useState<{
    amount: boolean;
    category: boolean;
    date: boolean;
  }>({ amount: false, category: false, date: false });
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const upload = useUploadReceipt();
  const create = useCreateExpense();

  const autoRing = (on: boolean) =>
    on ? "border-ochre bg-ochre/10 ring-1 ring-ochre" : "";

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setErrorMsg(null);
    setAutoFillNote(null);
    setSuccess(null);
    upload.mutate(file, {
      onSuccess: (data) => {
        // Auto-fill NEVER auto-submits — we only prefill the editable form.
        setReceiptPath(data.receiptPath);
        const f = data.parsed?.extractedFields;
        const nextFilled = { amount: false, category: false, date: false };
        if (f) {
          if (f.amount != null) {
            setAmount(String(f.amount));
            nextFilled.amount = true;
          }
          if (f.category) {
            setCategory(f.category);
            nextFilled.category = true;
          }
          if (f.date) {
            setExpenseDate(f.date);
            nextFilled.date = true;
          }
          const conf = data.parsed
            ? Math.round(data.parsed.confidence * 100)
            : 0;
          setAutoFillNote(
            `Auto-filled from receipt (${data.parsed?.docTypeGuess}, ${conf}% confidence). Review, then confirm to submit.`
          );
        } else {
          setAutoFillNote(
            "Receipt stored. Could not extract fields — enter manually."
          );
        }
        setFilled(nextFilled);
      },
      onError: (err) => setErrorMsg(extractErrorMessage(err)),
    });
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccess(null);
    const amt = parseFloat(amount);
    if (!amt || amt <= 0) {
      setErrorMsg("Enter a valid amount greater than 0.");
      return;
    }
    create.mutate(
      {
        amount: amt,
        category,
        description: description || undefined,
        expenseDate: expenseDate || undefined,
        receiptPath: receiptPath || undefined,
      },
      {
        onSuccess: (data) => {
          setSuccess(
            data.requiresFinance
              ? `Submitted ₹${data.amount} — routed to manager, then finance (≥ ₹${FINANCE_THRESHOLD}).`
              : `Submitted ₹${data.amount} — awaiting manager approval.`
          );
          setAmount("");
          setCategory("Travel");
          setDescription("");
          setExpenseDate("");
          setReceiptPath(null);
          setAutoFillNote(null);
          setFilled({ amount: false, category: false, date: false });
        },
        onError: (err) => setErrorMsg(extractErrorMessage(err)),
      }
    );
  };

  const amtNum = parseFloat(amount);
  const willNeedFinance = !isNaN(amtNum) && amtNum >= FINANCE_THRESHOLD;

  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-4 text-sm font-mono uppercase tracking-wide text-navy">
        New expense
      </h2>
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-inkSoft">
            Receipt (PDF or image) — auto-fills the form
          </label>
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.tiff,.bmp"
            onChange={onFile}
            className="w-full rounded border border-dashed border-line p-2 text-sm text-inkSoft file:mr-3 file:rounded file:border-0 file:bg-navy file:px-3 file:py-1.5 file:text-sm file:text-paper"
          />
          {upload.isPending ? (
            <p className="mt-1 text-xs text-inkSoft">Uploading & parsing…</p>
          ) : null}
          {autoFillNote ? (
            <p className="mt-1 text-xs text-ochre">{autoFillNote}</p>
          ) : null}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <FieldLabel autoFilled={filled.amount}>Amount (₹)</FieldLabel>
            <input
              type="number"
              step="0.01"
              min="0"
              required
              value={amount}
              onChange={(e) => {
                setAmount(e.target.value);
                setFilled((p) => ({ ...p, amount: false }));
              }}
              className={`w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2 ${autoRing(
                filled.amount
              )}`}
            />
          </div>
          <div>
            <FieldLabel autoFilled={filled.category}>Category</FieldLabel>
            <select
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setFilled((p) => ({ ...p, category: false }));
              }}
              className={`w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2 ${autoRing(
                filled.category
              )}`}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <FieldLabel autoFilled={filled.date}>Expense date</FieldLabel>
          <input
            type="date"
            value={expenseDate}
            onChange={(e) => {
              setExpenseDate(e.target.value);
              setFilled((p) => ({ ...p, date: false }));
            }}
            className={`w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2 ${autoRing(
              filled.date
            )}`}
          />
        </div>

        <div>
          <label className="mb-1 block text-xs font-medium text-inkSoft">
            Description (optional)
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={2}
            className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
          />
        </div>

        {willNeedFinance ? (
          <div className="rounded border border-navy/30 bg-navy/5 px-3 py-2 text-xs text-navy">
            This amount is ≥ ₹{FINANCE_THRESHOLD} — it needs manager approval,
            then finance sign-off before payout.
          </div>
        ) : null}

        {errorMsg ? (
          <div className="rounded border border-clay/40 bg-clay/10 px-3 py-2 text-sm text-clay">
            {errorMsg}
          </div>
        ) : null}
        {success ? (
          <div className="rounded border border-moss/40 bg-moss/10 px-3 py-2 text-sm text-moss">
            {success}
          </div>
        ) : null}

        <button
          type="submit"
          disabled={create.isPending}
          className="rounded bg-navy px-4 py-2 text-sm font-medium text-paper transition hover:bg-navy2 disabled:opacity-50"
        >
          {create.isPending ? "Submitting…" : "Confirm & submit expense"}
        </button>
      </form>
    </section>
  );
}

function MyExpenses() {
  const { data, isLoading } = useMyExpenses();
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 text-sm font-mono uppercase tracking-wide text-navy">
        My expenses
      </h2>
      {isLoading ? (
        <p className="text-sm text-inkSoft">Loading…</p>
      ) : !data || data.length === 0 ? (
        <p className="text-sm text-inkSoft">No expenses yet.</p>
      ) : (
        <div className="divide-y divide-line">
          {data.map((e: ExpenseRow) => (
            <div key={e.id} className="py-3 text-sm">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium text-ink">
                    ₹{e.amount} · {e.category}
                  </span>
                  <span className="ml-2 text-inkSoft">{e.expenseDate}</span>
                  {e.description ? (
                    <span className="ml-2 text-inkSoft">
                      — {e.description}
                    </span>
                  ) : null}
                </div>
                <StatusBadge status={e.status} />
              </div>
              <StatusTimeline row={e} />
              {e.hasReceipt ? (
                <div className="mt-1">
                  <ReceiptLink expenseId={e.id} />
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function DecisionRow({ e, stage }: { e: ExpenseRow; stage: "manager" | "finance" }) {
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const managerApprove = useManagerApproveExpense();
  const financeApprove = useFinanceApproveExpense();
  const reject = useRejectExpense();

  const busy =
    managerApprove.isPending || financeApprove.isPending || reject.isPending;

  const onApprove = () => {
    setErr(null);
    const mut = stage === "manager" ? managerApprove : financeApprove;
    mut.mutate(
      { expenseId: e.id, decisionNote: note || undefined },
      { onError: (x) => setErr(extractErrorMessage(x)) }
    );
  };
  const onReject = () => {
    setErr(null);
    reject.mutate(
      { expenseId: e.id, decisionNote: note || undefined },
      { onError: (x) => setErr(extractErrorMessage(x)) }
    );
  };

  return (
    <div className="py-3 text-sm">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-medium text-ink">
            {e.employeeName} · ₹{e.amount} · {e.category}
          </span>
          <span className="ml-2 text-inkSoft">{e.expenseDate}</span>
          {e.requiresFinance ? (
            <span className="ml-2 rounded-full bg-navy/10 px-1.5 py-0.5 text-[10px] font-semibold text-navy">
              needs finance
            </span>
          ) : null}
        </div>
        <StatusBadge status={e.status} />
      </div>
      {e.description ? (
        <p className="mt-0.5 text-xs text-inkSoft">{e.description}</p>
      ) : null}
      {e.hasReceipt ? (
        <div className="mt-1">
          <ReceiptLink expenseId={e.id} />
        </div>
      ) : null}
      <div className="mt-2 flex items-center gap-2">
        <input
          type="text"
          placeholder="Note (optional)"
          value={note}
          onChange={(ev) => setNote(ev.target.value)}
          className="flex-1 rounded border border-line bg-white px-2 py-1 text-xs text-ink focus:border-navy2"
        />
        <button
          type="button"
          disabled={busy}
          onClick={onApprove}
          className="rounded border border-moss bg-moss px-3 py-1 text-xs font-medium text-paper hover:opacity-90 disabled:opacity-50"
        >
          {stage === "finance" ? "Finance approve" : "Approve"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={onReject}
          className="rounded border border-clay px-3 py-1 text-xs font-medium text-clay hover:bg-clay/10 disabled:opacity-50"
        >
          Reject
        </button>
      </div>
      {err ? <p className="mt-1 text-xs text-clay">{err}</p> : null}
    </div>
  );
}

function ManagerQueue() {
  const { data, isLoading } = useExpenseQueue();
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 text-sm font-mono uppercase tracking-wide text-navy">
        Approval queue
      </h2>
      {isLoading ? (
        <p className="text-sm text-inkSoft">Loading…</p>
      ) : !data || data.length === 0 ? (
        <p className="text-sm text-inkSoft">Nothing awaiting your approval.</p>
      ) : (
        <div className="divide-y divide-line">
          {data.map((e) => (
            <DecisionRow key={e.id} e={e} stage="manager" />
          ))}
        </div>
      )}
    </section>
  );
}

function FinanceQueue() {
  const { data, isLoading } = useFinanceQueue();
  const [exporting, setExporting] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const onExport = async () => {
    setErr(null);
    setExporting(true);
    try {
      await downloadFinanceCsv();
    } catch (e) {
      setErr(extractErrorMessage(e));
    } finally {
      setExporting(false);
    }
  };
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-mono uppercase tracking-wide text-navy">
          Finance approval queue
        </h2>
        <button
          type="button"
          onClick={onExport}
          disabled={exporting}
          className="rounded border border-line px-3 py-1 text-xs font-medium text-inkSoft hover:bg-paper2 disabled:opacity-50"
        >
          {exporting ? "Exporting…" : "Export CSV"}
        </button>
      </div>
      {err ? <p className="mb-2 text-xs text-clay">{err}</p> : null}
      {isLoading ? (
        <p className="text-sm text-inkSoft">Loading…</p>
      ) : !data || data.length === 0 ? (
        <p className="text-sm text-inkSoft">
          Nothing awaiting finance sign-off.
        </p>
      ) : (
        <div className="divide-y divide-line">
          {data.map((e) => (
            <DecisionRow key={e.id} e={e} stage="finance" />
          ))}
        </div>
      )}
    </section>
  );
}

export default function ExpensesPage() {
  const { user } = useAuth();
  const role = user?.role;
  return (
    <PageShell title="Expenses">
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ExpenseForm />
        <MyExpenses />
        {role === "manager" || role === "hr_admin" ? <ManagerQueue /> : null}
        {role === "hr_admin" ? <FinanceQueue /> : null}
      </div>
    </PageShell>
  );
}
