"""E-receipt CSV parsing: map common column names to the canonical ledger fields."""

import csv
from collections import Counter

# Column aliases -> canonical field. Checked case-insensitively.
ALIASES = {
    "date": ["date", "order_date", "transaction_date", "purchase_date", "posted_date"],
    "vendor": ["vendor", "merchant", "merchant_name", "payee", "store", "supplier"],
    "total": ["total", "total_charged", "amount", "amount_charged", "amount_due", "grand_total", "total_paid"],
    "tax": ["tax", "tax_collected", "sales_tax", "tax_amount", "tax_total"],
    "payment_method": ["payment_method", "tender", "payment", "method", "paid_with", "card"],
    "description": ["description", "line", "line_item", "item", "item_description"],
}


def _build_column_map(fieldnames):
    lowered = {name.strip().lower(): name for name in fieldnames}
    mapping = {}
    for canonical, names in ALIASES.items():
        for name in names:
            if name in lowered:
                mapping[canonical] = lowered[name]
                break
    return mapping


def _to_float(value):
    try:
        return float(str(value).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def parse_csv_receipt(path: str) -> dict:
    """Parse an e-receipt CSV export into one ledger row.

    Line rows carry the item detail; the summary row (the one with the total)
    carries tax and payment method. Dates and vendor come from the most
    common non-empty value across rows.
    """
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")
        colmap = _build_column_map(reader.fieldnames)
        rows = list(reader)

    if not colmap.get("total") or not colmap.get("vendor"):
        raise ValueError(
            "CSV does not look like an e-receipt: need at least a vendor/merchant "
            "and a total/amount column"
        )

    summary_row = None
    for row in rows:
        if _to_float(row.get(colmap["total"])) is not None and _to_float(row.get(colmap["total"])) > 0:
            if summary_row is None or _to_float(row.get(colmap["total"])) >= _to_float(
                summary_row.get(colmap["total"])
            ):
                summary_row = row

    def most_common(field):
        name = colmap.get(field)
        if not name:
            return ""
        values = [str(r.get(name, "")).strip() for r in rows if str(r.get(name, "")).strip()]
        if not values:
            return ""
        return Counter(values).most_common(1)[0][0]

    total = _to_float(summary_row.get(colmap["total"])) if summary_row else None
    tax = _to_float(summary_row.get(colmap["tax"])) if summary_row and colmap.get("tax") else None
    if tax is None and colmap.get("tax"):
        tax_values = [_to_float(r.get(colmap["tax"])) for r in rows]
        tax_values = [v for v in tax_values if v is not None]
        tax = max(tax_values) if tax_values else 0.0

    payment = summary_row.get(colmap["payment_method"], "").strip() if summary_row and colmap.get("payment_method") else ""
    if not payment:
        payment = most_common("payment_method")

    from .vision import normalize_date

    return {
        "date": normalize_date(most_common("date")),
        "vendor": most_common("vendor"),
        "tax": tax or 0.0,
        "total": total if total is not None else 0.0,
        "payment_method": payment,
        "description": most_common("description"),
    }
