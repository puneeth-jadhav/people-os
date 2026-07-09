import { useMemo, useState } from "react";
import PageShell from "@/components/PageShell";
import { useAuth } from "@/context/AuthContext";
import { extractErrorMessage } from "@/lib/api";
import {
  downloadAcksCsv,
  fetchDownloadUrl,
  parseDocument,
  useAcknowledge,
  useDocumentSearch,
  useDocuments,
  useSaveIdNumbers,
  useUploadDocument,
  type DocumentRow,
  type ParsedDocument,
} from "@/api/documents";

const ALL_ROLES = ["employee", "manager", "hr_admin"];

function CategoryBadge({ category }: { category: string }) {
  const isPolicy = category === "policy";
  return (
    <span
      className={
        "rounded-full px-2 py-0.5 text-xs font-semibold " +
        (isPolicy
          ? "bg-navy/10 text-navy"
          : "bg-navy2/15 text-navy2")
      }
    >
      {isPolicy ? "Policy" : "Personal"}
    </span>
  );
}

function DownloadButton({ documentId }: { documentId: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const go = async () => {
    setBusy(true);
    setErr(null);
    try {
      const { url } = await fetchDownloadUrl(documentId);
      window.open(url, "_blank", "noopener");
    } catch (e) {
      setErr(extractErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <span className="inline-flex items-center gap-2">
      <button
        onClick={go}
        disabled={busy}
        className="rounded border border-line px-3 py-1 text-xs font-medium text-inkSoft transition hover:bg-paper2 disabled:opacity-50"
      >
        {busy ? "Preparing…" : "Download"}
      </button>
      {err ? <span className="text-xs text-clay">{err}</span> : null}
    </span>
  );
}

function DocRow({ doc }: { doc: DocumentRow }) {
  const ack = useAcknowledge();
  const [ackErr, setAckErr] = useState<string | null>(null);
  const needsAck = doc.requiresAck && doc.acknowledged === false;

  return (
    <div className="rounded border border-line bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <CategoryBadge category={doc.docCategory} />
            <span className="font-medium text-ink">{doc.title}</span>
            <span className="text-xs text-inkSoft">v{doc.version}</span>
          </div>
          <p className="mt-0.5 font-mono text-xs uppercase tracking-wide text-inkSoft">
            {doc.docType}
          </p>
          {doc.changeSummary ? (
            <p className="mt-1 rounded border border-ochre bg-ochre/10 px-2 py-1 text-xs text-ink">
              What changed: {doc.changeSummary}
            </p>
          ) : null}
        </div>
        <DownloadButton documentId={doc.id} />
      </div>

      {doc.requiresAck ? (
        <div className="mt-3 flex items-center gap-3">
          {doc.acknowledged ? (
            <span className="rounded-full bg-moss/15 px-2 py-0.5 text-xs font-medium text-moss">
              Acknowledged ✓
            </span>
          ) : (
            <>
              <button
                onClick={() =>
                  ack.mutate(doc.id, {
                    onError: (e) => setAckErr(extractErrorMessage(e)),
                  })
                }
                disabled={ack.isPending}
                className="rounded bg-navy px-3 py-1.5 text-xs font-medium text-paper transition hover:bg-navy2 disabled:opacity-50"
              >
                {ack.isPending ? "Acknowledging…" : "Acknowledge"}
              </button>
              {needsAck ? (
                <span className="text-xs text-ochre">
                  Requires your acknowledgement
                </span>
              ) : null}
              {ackErr ? (
                <span className="text-xs text-clay">{ackErr}</span>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </div>
  );
}

function SearchBox() {
  const [q, setQ] = useState("");
  const { data, isFetching } = useDocumentSearch(q);
  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-3 font-mono text-[10px] font-semibold uppercase tracking-[1.5px] text-navy">
        Search documents
      </h2>
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search titles and contents…"
        className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
      />
      {q.trim() ? (
        <div className="mt-3 space-y-2">
          {isFetching ? (
            <p className="text-sm text-inkSoft">Searching…</p>
          ) : !data || data.length === 0 ? (
            <p className="text-sm text-inkSoft">No results.</p>
          ) : (
            data.map((r) => (
              <div
                key={r.id}
                className="rounded border border-line px-3 py-2"
              >
                <div className="flex items-center gap-2">
                  <CategoryBadge category={r.docCategory} />
                  <span className="text-sm font-medium text-ink">
                    {r.title}
                  </span>
                  <span className="text-xs text-inkSoft">v{r.version}</span>
                </div>
                {r.snippet ? (
                  <p
                    className="mt-1 text-xs text-inkSoft"
                    dangerouslySetInnerHTML={{ __html: r.snippet }}
                  />
                ) : null}
              </div>
            ))
          )}
        </div>
      ) : null}
    </section>
  );
}

function UploadForm() {
  const upload = useUploadDocument();
  const [docCategory, setDocCategory] = useState<"policy" | "personal">(
    "policy"
  );
  const [title, setTitle] = useState("");
  const [docType, setDocType] = useState("");
  const [changeSummary, setChangeSummary] = useState("");
  const [requiresAck, setRequiresAck] = useState(false);
  const [visibleRoles, setVisibleRoles] = useState<string[]>([...ALL_ROLES]);
  const [ownerId, setOwnerId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const toggleRole = (r: string) =>
    setVisibleRoles((cur) =>
      cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r]
    );

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setMsg(null);
    setErr(null);
    if (!file) {
      setErr("Please choose a file.");
      return;
    }
    upload.mutate(
      {
        file,
        title,
        docCategory,
        docType,
        ownerId: docCategory === "personal" && ownerId ? ownerId : undefined,
        visibleRoles: docCategory === "policy" ? visibleRoles : undefined,
        requiresAck: docCategory === "policy" ? requiresAck : false,
        changeSummary: changeSummary || undefined,
      },
      {
        onSuccess: (d) => {
          setMsg(`Published “${d.title}” (v${d.version}).`);
          setTitle("");
          setDocType("");
          setChangeSummary("");
          setFile(null);
        },
        onError: (e2) => setErr(extractErrorMessage(e2)),
      }
    );
  };

  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-4 text-sm font-mono uppercase tracking-wide text-navy">
        Upload / publish document
      </h2>
      <form onSubmit={submit} className="space-y-3">
        <div className="flex gap-2">
          {(["policy", "personal"] as const).map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setDocCategory(c)}
              className={
                "rounded px-3 py-1.5 text-sm font-medium " +
                (docCategory === c
                  ? "bg-navy text-paper"
                  : "border border-line text-inkSoft hover:bg-paper2")
              }
            >
              {c === "policy" ? "Policy" : "Personal"}
            </button>
          ))}
        </div>
        <input
          required
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title"
          className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
        />
        <input
          required
          value={docType}
          onChange={(e) => setDocType(e.target.value)}
          placeholder="Doc type (e.g. leave_policy, payslip)"
          className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
        />
        {docCategory === "personal" ? (
          <input
            value={ownerId}
            onChange={(e) => setOwnerId(e.target.value)}
            placeholder="Owner employee id (blank = you)"
            className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
          />
        ) : (
          <>
            <input
              value={changeSummary}
              onChange={(e) => setChangeSummary(e.target.value)}
              placeholder="Change summary (what changed in this version)"
              className="w-full rounded border border-line bg-white px-3 py-2 text-sm text-ink focus:border-navy2"
            />
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="text-inkSoft">Visible to:</span>
              {ALL_ROLES.map((r) => (
                <label key={r} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={visibleRoles.includes(r)}
                    onChange={() => toggleRole(r)}
                  />
                  {r}
                </label>
              ))}
              <label className="flex items-center gap-1">
                <input
                  type="checkbox"
                  checked={requiresAck}
                  onChange={(e) => setRequiresAck(e.target.checked)}
                />
                requires acknowledgement
              </label>
            </div>
          </>
        )}
        <input
          type="file"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm"
        />
        {err ? (
          <div className="rounded border border-clay/40 bg-clay/10 px-3 py-2 text-sm text-clay">
            {err}
          </div>
        ) : null}
        {msg ? (
          <div className="rounded border border-moss/40 bg-moss/10 px-3 py-2 text-sm text-moss">
            {msg}
          </div>
        ) : null}
        <button
          type="submit"
          disabled={upload.isPending}
          className="rounded bg-navy px-4 py-2 text-sm font-medium text-paper transition hover:bg-navy2 disabled:opacity-50"
        >
          {upload.isPending ? "Uploading…" : "Publish"}
        </button>
      </form>
    </section>
  );
}

// Self-service ID upload with OCR auto-fill. Visible to ALL logged-in users.
// Flow: pick file -> parse (OCR) -> review/edit pre-filled values -> confirm,
// which persists the file as a private personal document AND writes the
// confirmed Aadhaar/PAN onto the user's own profile. Never auto-submits.
function IdUploadCard() {
  const upload = useUploadDocument();
  const saveIds = useSaveIdNumbers();

  const [file, setFile] = useState<File | null>(null);
  const [parsing, setParsing] = useState(false);
  const [parsed, setParsed] = useState<ParsedDocument | null>(null);

  const [aadhaar, setAadhaar] = useState("");
  const [pan, setPan] = useState("");
  const [dob, setDob] = useState("");
  const [name, setName] = useState("");

  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const busy = parsing || saving;
  const highlight =
    "rounded border border-ochre bg-ochre/10 px-3 py-2 text-sm text-ink focus:border-ochre focus:outline-none focus:ring-1 focus:ring-ochre";

  const onPick = async (f: File | null) => {
    setFile(f);
    setParsed(null);
    setErr(null);
    setMsg(null);
    setAadhaar("");
    setPan("");
    setDob("");
    setName("");
    if (!f) return;
    setParsing(true);
    try {
      const result = await parseDocument(f);
      setParsed(result);
      const ef = result.extractedFields ?? {};
      setAadhaar(ef.aadhaar ?? "");
      setPan(ef.pan ?? "");
      setDob(ef.dateOfBirth ?? "");
      setName((ef.name as string) ?? "");
    } catch (e) {
      setErr(extractErrorMessage(e));
    } finally {
      setParsing(false);
    }
  };

  const onConfirm = async () => {
    if (!file) return;
    setErr(null);
    setMsg(null);
    setSaving(true);
    try {
      const docType = parsed?.docTypeGuess || "ID";
      await upload.mutateAsync({
        file,
        title: `${docType} - ${name || "Document"}`,
        docCategory: "personal",
        docType: "id_document",
      });
      const idPayload: { aadhaarNumber?: string; panNumber?: string } = {};
      if (aadhaar.trim()) idPayload.aadhaarNumber = aadhaar.trim();
      if (pan.trim()) idPayload.panNumber = pan.trim();
      if (idPayload.aadhaarNumber || idPayload.panNumber) {
        await saveIds.mutateAsync(idPayload);
      }
      setMsg("Saved. Your ID document and details have been recorded.");
      setFile(null);
      setParsed(null);
      setAadhaar("");
      setPan("");
      setDob("");
      setName("");
    } catch (e) {
      setErr(extractErrorMessage(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
      <h2 className="mb-1 text-sm font-mono uppercase tracking-wide text-navy">
        Upload ID document (Aadhaar / PAN)
      </h2>
      <p className="mb-3 text-xs text-inkSoft">
        Upload your ID and we'll auto-fill the details for you to review before
        saving.
      </p>

      <input
        type="file"
        onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        disabled={busy}
        className="block w-full text-sm"
      />

      {parsing ? (
        <p className="mt-3 text-sm text-inkSoft">Reading document…</p>
      ) : null}

      {parsed ? (
        <div className="mt-4 space-y-3">
          <p className="text-xs text-ochre">
            Auto-filled from your document — please review and edit if needed.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs font-medium text-inkSoft">
              Aadhaar number
              <input
                value={aadhaar}
                onChange={(e) => setAadhaar(e.target.value)}
                placeholder="1234 5678 9012"
                className={highlight}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-inkSoft">
              PAN
              <input
                value={pan}
                onChange={(e) => setPan(e.target.value.toUpperCase())}
                placeholder="ABCDE1234F"
                className={highlight}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-inkSoft">
              Date of birth
              <input
                value={dob}
                onChange={(e) => setDob(e.target.value)}
                placeholder="YYYY-MM-DD"
                className={highlight}
              />
            </label>
            <label className="flex flex-col gap-1 text-xs font-medium text-inkSoft">
              Name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Full name"
                className={highlight}
              />
            </label>
          </div>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="rounded bg-navy px-4 py-2 text-sm font-medium text-paper transition hover:bg-navy2 disabled:opacity-50"
          >
            {saving ? "Saving…" : "Confirm & save"}
          </button>
        </div>
      ) : null}

      {err ? (
        <div className="mt-3 rounded border border-clay/40 bg-clay/10 px-3 py-2 text-sm text-clay">
          {err}
        </div>
      ) : null}
      {msg ? (
        <div className="mt-3 rounded border border-moss/40 bg-moss/10 px-3 py-2 text-sm text-moss">
          {msg}
        </div>
      ) : null}
    </section>
  );
}


export default function DocumentsPage() {
  const { user } = useAuth();
  const isHr = user?.role === "hr_admin";
  const { data, isLoading } = useDocuments();

  const { personal, policies } = useMemo(() => {
    const list = data ?? [];
    return {
      personal: list.filter((d) => d.docCategory === "personal"),
      policies: list.filter((d) => d.docCategory === "policy"),
    };
  }, [data]);

  const [exportErr, setExportErr] = useState<string | null>(null);

  return (
    <PageShell title="Documents">
      <SearchBox />

      <IdUploadCard />

      <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-mono uppercase tracking-wide text-navy">
          My documents
        </h2>
        {isLoading ? (
          <p className="text-sm text-inkSoft">Loading…</p>
        ) : personal.length === 0 ? (
          <p className="text-sm text-inkSoft">No personal documents.</p>
        ) : (
          <div className="space-y-2">
            {personal.map((d) => (
              <DocRow key={d.id} doc={d} />
            ))}
          </div>
        )}
      </section>

      <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
        <h2 className="mb-3 text-sm font-mono uppercase tracking-wide text-navy">
          Policies & company documents
        </h2>
        {isLoading ? (
          <p className="text-sm text-inkSoft">Loading…</p>
        ) : policies.length === 0 ? (
          <p className="text-sm text-inkSoft">No policy documents.</p>
        ) : (
          <div className="space-y-2">
            {policies.map((d) => (
              <DocRow key={d.id} doc={d} />
            ))}
          </div>
        )}
      </section>

      {isHr ? (
        <>
          <UploadForm />
          <section className="rounded border border-line border-t-4 border-t-navy bg-card p-5 shadow-sm">
            <h2 className="mb-3 text-sm font-mono uppercase tracking-wide text-navy">
              Compliance
            </h2>
            <button
              onClick={() =>
                downloadAcksCsv().catch((e) =>
                  setExportErr(extractErrorMessage(e))
                )
              }
              className="rounded border border-line px-3 py-2 text-sm font-medium text-inkSoft transition hover:bg-paper2"
            >
              Export acknowledgements (CSV)
            </button>
            {exportErr ? (
              <span className="ml-3 text-sm text-clay">{exportErr}</span>
            ) : null}
          </section>
        </>
      ) : null}
    </PageShell>
  );
}
