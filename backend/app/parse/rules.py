"""Deterministic field-extraction rules for receipt/document parsing (Phase 5).

Pure functions + keyword maps. No network, no LLM. Used by parser.parse_document.
"""

import re
from datetime import date

# ---------------------------------------------------------------------------
# Currency / amounts
# ---------------------------------------------------------------------------

# Matches ₹4,850 / Rs 4850 / Rs. 4,850 / INR 4850 / 4,850.00 / 55,000
_AMOUNT_RE = re.compile(
    r"(?:₹|rs\.?|inr)?\s*"
    r"(\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)",
    re.IGNORECASE,
)

_AMOUNT_KEYWORDS = ("total", "net pay", "net", "amount", "grand total", "balance due")


def _to_float(raw: str) -> float | None:
    cleaned = raw.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_amounts(text: str) -> list[float]:
    """Return every currency-like numeric amount found in text (as floats)."""
    amounts: list[float] = []
    for m in _AMOUNT_RE.finditer(text or ""):
        val = _to_float(m.group(1))
        if val is not None:
            amounts.append(val)
    return amounts


def best_amount(text: str) -> float | None:
    """Choose the amount near a keyword like 'total'/'net'/'amount', else largest."""
    if not text:
        return None
    lower = text.lower()

    keyword_amounts: list[float] = []
    for line in text.splitlines():
        ll = line.lower()
        if any(k in ll for k in _AMOUNT_KEYWORDS):
            keyword_amounts.extend(extract_amounts(line))
    if keyword_amounts:
        return max(keyword_amounts)

    # Fallback: search a window after any keyword occurrence in the flat text.
    for kw in _AMOUNT_KEYWORDS:
        idx = lower.find(kw)
        if idx != -1:
            window = text[idx: idx + 80]
            amts = extract_amounts(window)
            if amts:
                return max(amts)

    all_amounts = extract_amounts(text)
    return max(all_amounts) if all_amounts else None


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}

_ISO_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DMY_RE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")
# 'DD Mon YYYY' e.g. 12 Mar 2024
_DMONY_RE = re.compile(
    r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})\b"
)
# 'Mon DD, YYYY' e.g. Mar 12, 2024
_MONDY_RE = re.compile(
    r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b"
)

_DATE_KEYWORDS = ("invoice date", "dated", "date")


def _safe_iso(y: int, mo: int, d: int) -> str | None:
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def _dates_from_text(text: str) -> list[tuple[int, str]]:
    """Return (position, iso) tuples for every date found."""
    found: list[tuple[int, str]] = []

    for m in _ISO_RE.finditer(text):
        iso = _safe_iso(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if iso:
            found.append((m.start(), iso))

    for m in _DMY_RE.finditer(text):
        iso = _safe_iso(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        if iso:
            found.append((m.start(), iso))

    for m in _DMONY_RE.finditer(text):
        mon = _MONTHS.get(m.group(2).lower())
        if mon:
            iso = _safe_iso(int(m.group(3)), mon, int(m.group(1)))
            if iso:
                found.append((m.start(), iso))

    for m in _MONDY_RE.finditer(text):
        mon = _MONTHS.get(m.group(1).lower())
        if mon:
            iso = _safe_iso(int(m.group(3)), mon, int(m.group(2)))
            if iso:
                found.append((m.start(), iso))

    return found


def extract_dates(text: str) -> list[str]:
    """Return all recognized dates as ISO yyyy-mm-dd strings (in order)."""
    found = _dates_from_text(text or "")
    found.sort(key=lambda t: t[0])
    seen: set[str] = set()
    out: list[str] = []
    for _, iso in found:
        if iso not in seen:
            seen.add(iso)
            out.append(iso)
    return out


def best_date(text: str) -> str | None:
    """Prefer a date near 'date'/'invoice date'/'dated', else the first date."""
    if not text:
        return None
    found = _dates_from_text(text)
    if not found:
        return None

    lower = text.lower()
    best: tuple[int, str] | None = None
    best_dist: int | None = None
    for kw in _DATE_KEYWORDS:
        start = 0
        while True:
            idx = lower.find(kw, start)
            if idx == -1:
                break
            start = idx + 1
            for pos, iso in found:
                dist = abs(pos - idx)
                if dist <= 40 and (best_dist is None or dist < best_dist):
                    best_dist = dist
                    best = (pos, iso)
    if best is not None:
        return best[1]

    found.sort(key=lambda t: t[0])
    return found[0][1]


_DOB_KEYWORDS = ("date of birth", "d.o.b", "dob", "birth")


def extract_dob(text: str) -> str | None:
    """Prefer a date near a DOB keyword; else return None."""
    if not text:
        return None
    found = _dates_from_text(text)
    if not found:
        return None

    lower = text.lower()
    best: tuple[int, str] | None = None
    best_dist: int | None = None
    for kw in _DOB_KEYWORDS:
        start = 0
        while True:
            idx = lower.find(kw, start)
            if idx == -1:
                break
            start = idx + 1
            for pos, iso in found:
                dist = abs(pos - idx)
                if dist <= 40 and (best_dist is None or dist < best_dist):
                    best_dist = dist
                    best = (pos, iso)
    if best is not None:
        return best[1]
    return None


# ---------------------------------------------------------------------------
# Government ID numbers (Aadhaar / PAN)
# ---------------------------------------------------------------------------

_AADHAAR_RE = re.compile(r"\b(\d{4}[\s-]?\d{4}[\s-]?\d{4})\b")
_PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")


def extract_aadhaar(text: str) -> str | None:
    """Return a normalized 12-digit Aadhaar number if found, else None."""
    for m in _AADHAAR_RE.finditer(text or ""):
        digits = re.sub(r"\D", "", m.group(1))
        if len(digits) == 12:
            return digits
    return None


def extract_pan(text: str) -> str | None:
    """Return an uppercase 10-char PAN if found, else None."""
    m = _PAN_RE.search((text or "").upper())
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def extract_emails(text: str) -> list[str]:
    """Return all email addresses found in text."""
    return _EMAIL_RE.findall(text or "")


# ---------------------------------------------------------------------------
# Labeled fields
# ---------------------------------------------------------------------------

_LABEL_MAP = {
    "name": "name",
    "date of joining": "dateOfJoining",
    "department": "department",
    "designation": "designation",
}


def extract_labeled(text: str) -> dict:
    """Extract labeled fields (Name:, Date of Joining:, Department:, Designation:)."""
    out: dict = {}
    for line in (text or "").splitlines():
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        key = _LABEL_MAP.get(label.strip().lower())
        value = value.strip()
        if key and value and key not in out:
            if key == "dateOfJoining":
                iso = extract_dates(value)
                out[key] = iso[0] if iso else value
            else:
                out[key] = value
    return out


# ---------------------------------------------------------------------------
# Expense category mapping
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS = [
    ("Travel", ("uber", "ola", "fuel", "cab", "taxi", "petrol", "diesel")),
    ("Lodging", ("hotel", "lodge", "stay", "resort", "inn")),
    ("Meals", ("restaurant", "cafe", "café", "food", "dining", "meal", "diner")),
]


def category_for(text: str) -> str:
    """Map text to an expense category via keyword maps; default 'Other'."""
    lower = (text or "").lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        if any(k in lower for k in keywords):
            return category
    return "Other"


# ---------------------------------------------------------------------------
# Document-type scoring
# ---------------------------------------------------------------------------

_DOCTYPE_KEYWORDS = [
    ("Payslip", ("payslip", "net pay", "salary", "gross pay", "pay slip")),
    ("Invoice", ("tax invoice", "invoice", "gst", "total", "tax")),
    ("Offer Letter", ("offer letter", "appointment", "offer", "ctc", "joining")),
    ("ID Document", ("aadhaar", "aadhar", "uidai", "permanent account number",
                     "income tax", "govt of india", "government of india")),
]


def doctype_and_confidence(text: str) -> tuple[str, float]:
    """Score keyword hits to guess doctype and a [0,1] confidence."""
    lower = (text or "").lower()

    scores: dict[str, int] = {}
    considered: dict[str, int] = {}
    for doctype, keywords in _DOCTYPE_KEYWORDS:
        considered[doctype] = len(keywords)
        scores[doctype] = sum(1 for k in keywords if k in lower)

    best_type = max(scores, key=lambda t: scores[t])
    if scores[best_type] == 0:
        return "Other", 0.3

    confidence = scores[best_type] / max(1, considered[best_type])
    confidence = round(max(0.0, min(1.0, confidence)), 2)
    return best_type, confidence
