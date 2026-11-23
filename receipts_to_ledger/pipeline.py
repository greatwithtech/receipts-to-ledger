"""Pipeline: walk an input folder, extract one ledger row per file, write one CSV."""

import csv
import os
import sys
from dataclasses import dataclass

from . import categorize
from .csvparse import parse_csv_receipt
from .pdfrender import first_page_png
from .textparse import parse_text_receipt
from .vision import MissingKeyError, extract_from_image_bytes, get_client

IMAGE_EXTS = {".png", ".jpg", ".jpeg"}
SUPPORTED_EXTS = IMAGE_EXTS | {".pdf", ".txt", ".csv"}

LEDGER_COLUMNS = ["date", "vendor", "amount", "tax", "category", "payment_method"]


@dataclass
class Row:
    date: str
    vendor: str
    amount: float
    tax: float
    category: str
    payment_method: str
    source_file: str
    status: str = "ok"  # or "error"
    detail: str = ""


def _process_one(path: str, client, model: str) -> Row:
    ext = os.path.splitext(path)[1].lower()
    name = os.path.basename(path)

    if ext in IMAGE_EXTS:
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
        with open(path, "rb") as f:
            data = extract_from_image_bytes(f.read(), mime, client=client, model=model)
        items = [{"description": i.description, "quantity": i.quantity, "unit_price": i.unit_price} for i in data.line_items]
        raw = {"date": data.date, "vendor": data.vendor, "tax": data.tax, "total": data.total,
               "payment_method": data.payment_method, "description": ""}
        line_items = items

    elif ext == ".pdf":
        png_bytes = first_page_png(path)
        data = extract_from_image_bytes(png_bytes, "image/png", client=client, model=model)
        items = [{"description": i.description, "quantity": i.quantity, "unit_price": i.unit_price} for i in data.line_items]
        raw = {"date": data.date, "vendor": data.vendor, "tax": data.tax, "total": data.total,
               "payment_method": data.payment_method, "description": ""}
        line_items = items

    elif ext == ".txt":
        with open(path, encoding="utf-8", errors="replace") as f:
            raw = parse_text_receipt(f.read())
        line_items = []

    elif ext == ".csv":
        raw = parse_csv_receipt(path)
        line_items = []

    else:
        raise ValueError(f"unsupported file type: {ext}")

    category = categorize.categorize(raw["vendor"], raw.get("description", ""), line_items)
    return Row(
        date=raw["date"],
        vendor=raw["vendor"],
        amount=round(float(raw["total"]), 2),
        tax=round(float(raw["tax"]), 2),
        category=category,
        payment_method=raw["payment_method"],
        source_file=name,
    )


def _date_sort_key(date_str: str):
    # ISO dates sort correctly as strings; unparseable dates go last, preserving file order.
    if len(date_str) == 10 and date_str[4] == "-" and date_str[:4].isdigit():
        return (0, date_str)
    return (1, "9999-99-99")


def process_folder(input_dir: str, output_csv: str = None, model: str = None, quiet: bool = False):
    """Process every supported file in input_dir. Returns (rows, output_csv_path).

    Rows are sorted by date. When output_csv is given (or defaults to
    output/ledger.csv), the ledger is written there.
    """
    if not os.path.isdir(input_dir):
        raise SystemExit(f"input folder not found: {input_dir}")

    try:
        client = get_client()
    except MissingKeyError as e:
        raise SystemExit(str(e))

    files = sorted(
        os.path.join(input_dir, f)
        for f in os.listdir(input_dir)
        if not f.startswith(".")
        and os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
        and os.path.isfile(os.path.join(input_dir, f))
    )
    if not files:
        raise SystemExit(f"no supported files (.png .jpg .jpeg .pdf .txt .csv) in {input_dir}")

    rows = []
    for path in files:
        name = os.path.basename(path)
        try:
            row = _process_one(path, client, model)
            rows.append(row)
            if not quiet:
                print(f"  ok    {name:<40} {row.date}  {row.vendor[:30]:<30} ${row.amount:>9.2f}")
        except Exception as e:  # keep going; report at the end
            rows.append(Row(date="", vendor="", amount=0.0, tax=0.0, category="",
                            payment_method="", source_file=name, status="error", detail=str(e)))
            if not quiet:
                print(f"  FAIL  {name:<40} {e}")

    rows.sort(key=lambda r: (_date_sort_key(r.date), r.source_file))

    if output_csv is None:
        output_csv = os.path.join("output", "ledger.csv")
    os.makedirs(os.path.dirname(output_csv) or ".", exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(LEDGER_COLUMNS)
        for row in rows:
            if row.status == "ok":
                writer.writerow([row.date, row.vendor, f"{row.amount:.2f}", f"{row.tax:.2f}",
                                 row.category, row.payment_method])

    # Run report to stdout
    ok_rows = [r for r in rows if r.status == "ok"]
    failed = [r for r in rows if r.status == "error"]
    total = sum(r.amount for r in ok_rows)
    tax_total = sum(r.tax for r in ok_rows)
    print()
    print(f"run report: {len(ok_rows)} of {len(rows)} files extracted, {len(failed)} failed")
    if failed:
        for r in failed:
            print(f"  failed: {r.source_file}: {r.detail}")
    print(f"ledger written to {output_csv}")
    print(f"total: ${total:.2f} across {len(ok_rows)} receipts (tax ${tax_total:.2f})")
    return rows, output_csv
