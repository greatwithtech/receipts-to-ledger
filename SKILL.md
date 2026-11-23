---
name: receipts-to-ledger
description: Turn a folder of receipts and invoices (phone photos, scans, PDFs, e-receipt CSVs, pasted confirmation emails) into one accountant-ready ledger CSV with date, vendor, amount, tax, category, and payment method, checked by a fixture-based end-to-end test suite. Use when someone hands you a pile of receipt files and needs a single expense spreadsheet, when running the receipts-to-ledger pipeline, or when running its fixture tests.
---

# receipts-to-ledger

## When to use

Use this skill when the task is to convert a folder of receipt and invoice files
into one ledger spreadsheet. It handles the common small-business mix: phone
photos of paper receipts, PDF invoices, e-receipt CSV exports, and pasted
confirmation emails.

## Setup (once)

```bash
cd <repo checkout>
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...   # from platform.openai.com
```

If `OPENAI_API_KEY` is missing, the pipeline exits with a clear message instead
of failing halfway.

## Run

```bash
python -m receipts_to_ledger ./path/to/receipts -o ledger.csv
```

- Input: one folder. One receipt per file. Supported: `.png .jpg .jpeg .pdf .txt .csv`.
- Output: `ledger.csv` with columns `date, vendor, amount, tax, category, payment_method`, sorted by date.
- A run report prints to stdout: per-file status, failures, and totals.

Optional: `--model` picks the vision model (default `gpt-4o-mini`, overridable
via `RECEIPTS_TO_LEDGER_MODEL`).

## How extraction works

- Images and PDFs go to the OpenAI vision model with a strict JSON schema
  (PyMuPDF renders the PDF first page to an image first). The prompt asks for
  ISO dates and character-for-character payment strings.
- `.txt` files are parsed with regexes for the date, amount, and payment lines;
  the vendor comes from the sender domain.
- `.csv` files are mapped from common column names (`merchant`, `total_charged`,
  `tender`, and similar) to the canonical fields.
- Categories come from a keyword rules list in
  `receipts_to_ledger/categorize.py`. Edit that file to match a chart of
  accounts.

## Check the result with the test suite

```bash
pytest -q
```

The tests run the pipeline on `fixtures/receipts/` (12 fictional files) and
compare with `fixtures/golden.csv`: amounts and tax to the cent, dates after
normalization, vendors at 0.85 fuzzy match or higher, payment methods exact,
categories present. The fixtures are seeded and deterministic.

If a test fails, fix the prompt or parsing code. Do not weaken the assertions;
the fixtures are the ground truth. The tests call the OpenAI API (about 10
vision requests per run) and skip with a message when `OPENAI_API_KEY` is not
set.

## Limits to state up front

- One receipt per file; multi-page invoices are not supported (first PDF page only).
- English only.
- Accuracy depends on image quality; small print such as masked card numbers is the likely misread.
- Categories are keyword-based, not model-generated.
- The output is a starting point for bookkeeping, not a replacement for an accountant's review.
