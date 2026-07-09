"""Compose deterministic rule functions into structured document fields (Phase 5)."""

from app.parse import rules


def parse_document(text: str) -> dict:
    """Parse extracted text into structured, camelCase fields. Deterministic."""
    text = text or ""

    doc_type, confidence = rules.doctype_and_confidence(text)

    labeled = rules.extract_labeled(text)
    emails = rules.extract_emails(text)

    extracted_fields = {
        "amount": rules.best_amount(text),
        "date": rules.best_date(text),
        "category": rules.category_for(text),
        "email": emails[0] if emails else None,
        "name": labeled.get("name"),
        "dateOfJoining": labeled.get("dateOfJoining"),
        "department": labeled.get("department"),
        "designation": labeled.get("designation"),
        "aadhaar": rules.extract_aadhaar(text),
        "pan": rules.extract_pan(text),
        "dateOfBirth": rules.extract_dob(text),
    }

    return {
        "docTypeGuess": doc_type,
        "confidence": confidence,
        "extractedFields": extracted_fields,
    }
