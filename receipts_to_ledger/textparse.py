"""Plain-text receipt parsing: regex heuristics for pasted email receipts."""

import re

from .vision import normalize_date

DATE_PATTERNS = [
    r"Date(?:\s*charged)?\s*[:\-]\s*([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})",
    r"Date(?:\s*charged)?\s*[:\-]\s*([0-9]{4}-[0-9]{2}-[0-9]{2})",
    r"Date(?:\s*charged)?\s*[:\-]\s*([A-Za-z]+ [0-9]{1,2},? [0-9]{4})",
]

AMOUNT_PATTERN = re.compile(
    r"(?:amount\s+charged|amount\s+due|total\s+charged|total|amount)\s*[:\-]?\s*\$?\s*([0-9][0-9,]*\.[0-9]{2})",
    re.IGNORECASE,
)
TAX_PATTERN = re.compile(r"tax\s*[:\-]?\s*\$?\s*([0-9][0-9,]*\.[0-9]{2})", re.IGNORECASE)
PAYMENT_PATTERN = re.compile(
    r"(?:payment\s+method|paid\s+by|paid\s+via|method|paid\s+with)\s*[:\-]\s*(.+)",
    re.IGNORECASE,
)
FROM_PATTERN = re.compile(r"From\s*:\s*.*@([A-Za-z0-9.\-]+)", re.IGNORECASE)

# Email-only domains to skip when guessing the vendor from a sender address.
GENERIC_DOMAINS = {"gmail.com", "outlook.com", "yahoo.com", "icloud.com", "example.com", "example.org"}


def parse_text_receipt(text: str) -> dict:
    """Parse a pasted email/text receipt. Returns a dict with date, vendor, tax, total,
    payment_method, and a short description when available."""
    result = {"date": "", "vendor": "", "tax": 0.0, "total": 0.0, "payment_method": "", "description": ""}

    for pattern in DATE_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            result["date"] = normalize_date(m.group(1))
            if result["date"]:
                break

    amounts = AMOUNT_PATTERN.findall(text)
    if amounts:
        # The largest dollar figure in the message is the amount charged.
        result["total"] = max(float(a.replace(",", "")) for a in amounts)

    m = TAX_PATTERN.search(text)
    if m:
        result["tax"] = float(m.group(1).replace(",", ""))

    m = PAYMENT_PATTERN.search(text)
    if m:
        result["payment_method"] = m.group(1).strip().rstrip(".")

    m = FROM_PATTERN.search(text)
    if m:
        domain = m.group(1).lower()
        if domain not in GENERIC_DOMAINS:
            label = domain.split(".")[0]
            result["vendor"] = label.replace("-", " ").strip().title()

    m = re.search(r"Description\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if m:
        result["description"] = m.group(1).strip()

    return result
