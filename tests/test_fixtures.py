"""End-to-end tests: run the full pipeline on fixtures/receipts/ and compare the
result against fixtures/golden.csv.

These tests call the OpenAI API (roughly one vision request per image file), so
they need OPENAI_API_KEY in the environment. The fixtures are generated with a
fixed seed, so the expected values never change between runs.

Run:  pytest -q
"""

import csv
import difflib
import os
from pathlib import Path

import pytest

from receipts_to_ledger.pipeline import LEDGER_COLUMNS, process_folder

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_RECEIPTS = REPO_ROOT / "fixtures" / "receipts"
GOLDEN_CSV = REPO_ROOT / "fixtures" / "golden.csv"

VENDOR_MATCH_THRESHOLD = 0.85
CENT = 0.005  # tolerance for cent-level comparisons

pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is not set; this suite runs the real pipeline end to end",
)


# ------------------------------------------------------------------ helpers

def load_golden():
    with open(GOLDEN_CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def vendor_similarity(a: str, b: str) -> float:
    """Case-insensitive vendor similarity in [0, 1]."""
    return difflib.SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def pair_golden_with_ledger(golden_rows, ledger_rows):
    """Greedy one-to-one matching of golden rows to ledger rows by vendor similarity.

    Returns a list of (golden_row, ledger_row) and raises AssertionError if any
    golden row cannot be matched to a distinct ledger row above the threshold.
    """
    candidates = []
    for g in golden_rows:
        for i, l in enumerate(ledger_rows):
            score = vendor_similarity(g["vendor"], l.vendor)
            if score >= VENDOR_MATCH_THRESHOLD:
                candidates.append((score, g["vendor"], i, g, l))
    candidates.sort(reverse=True, key=lambda c: c[0])

    matched, used_indices = [], set()
    for score, _, i, g, l in candidates:
        if i in used_indices or g in [m[0] for m in matched]:
            continue
        matched.append((g, l))
        used_indices.add(i)

    unmatched = [g["vendor"] for g in golden_rows if g not in [m[0] for m in matched]]
    assert not unmatched, f"no ledger row matched these golden vendors: {unmatched}"
    return matched


# ----------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def pipeline_run(tmp_path_factory):
    """Run the pipeline once on the fixture folder; reuse the result in every test."""
    output_csv = tmp_path_factory.mktemp("out") / "ledger.csv"
    rows, out_path = process_folder(str(FIXTURE_RECEIPTS), output_csv=str(output_csv), quiet=True)
    return rows, out_path


@pytest.fixture(scope="module")
def ledger_rows(pipeline_run):
    return pipeline_run[0]


@pytest.fixture(scope="module")
def matched_pairs(ledger_rows):
    return pair_golden_with_ledger(load_golden(), ledger_rows)


# -------------------------------------------------------------------- tests

def test_every_input_file_produced_a_row(ledger_rows):
    files = sorted(p.name for p in FIXTURE_RECEIPTS.iterdir() if not p.name.startswith("."))
    extracted = [r.source_file for r in ledger_rows]
    assert sorted(extracted) == files, f"expected one row per file, got: {extracted}"
    failed = [r for r in ledger_rows if r.status == "error"]
    assert not failed, f"pipeline errored on: {[(r.source_file, r.detail) for r in failed]}"


def test_every_golden_row_matched_a_ledger_row(matched_pairs):
    golden = load_golden()
    assert len(matched_pairs) == len(golden) == 12


def test_amounts_exact_to_the_cent(matched_pairs):
    for golden, row in matched_pairs:
        assert abs(row.amount - float(golden["amount"])) <= CENT, (
            f"{golden['vendor']}: got {row.amount}, expected {golden['amount']}"
        )


def test_tax_exact_to_the_cent(matched_pairs):
    for golden, row in matched_pairs:
        assert abs(row.tax - float(golden["tax"])) <= CENT, (
            f"{golden['vendor']}: got {row.tax}, expected {golden['tax']}"
        )


def test_dates_exact_after_normalization(matched_pairs):
    for golden, row in matched_pairs:
        assert row.date == golden["date"], (
            f"{golden['vendor']}: got {row.date}, expected {golden['date']}"
        )


def test_payment_methods_exact(matched_pairs):
    for golden, row in matched_pairs:
        assert row.payment_method == golden["payment_method"], (
            f"{golden['vendor']}: got '{row.payment_method}', expected '{golden['payment_method']}'"
        )


def test_categories_present(matched_pairs):
    missing = [g["vendor"] for g, row in matched_pairs if not row.category.strip()]
    assert not missing, f"no category assigned for: {missing}"


def test_vendors_match_closely(matched_pairs):
    for golden, row in matched_pairs:
        score = vendor_similarity(golden["vendor"], row.vendor)
        assert score >= VENDOR_MATCH_THRESHOLD, (
            f"'{row.vendor}' vs '{golden['vendor']}' scored {score:.2f}"
        )


def test_ledger_csv_is_sorted_by_date(ledger_rows):
    ok_rows = [r for r in ledger_rows if r.status == "ok"]
    dates = [r.date for r in ok_rows]
    assert dates == sorted(dates), f"ledger rows not sorted by date: {dates}"


def test_ledger_csv_has_canonical_columns(pipeline_run):
    _, out_path = pipeline_run
    with open(out_path, newline="", encoding="utf-8") as f:
        header = next(csv.reader(f))
    assert header == LEDGER_COLUMNS
