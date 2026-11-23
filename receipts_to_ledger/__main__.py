"""Command line entry point: python -m receipts_to_ledger <input_folder>"""

import argparse
import sys

from .pipeline import process_folder


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="receipts-to-ledger",
        description="Turn a folder of receipts and invoices into one ledger CSV.",
    )
    parser.add_argument("input_folder", help="folder containing receipt images, PDFs, CSVs, and txt files")
    parser.add_argument("-o", "--output", default="output/ledger.csv", help="output CSV path (default: output/ledger.csv)")
    parser.add_argument("--model", default=None, help="OpenAI vision model (default: gpt-4o-mini, overridable via RECEIPTS_TO_LEDGER_MODEL)")
    args = parser.parse_args(argv)

    rows, out = process_folder(args.input_folder, output_csv=args.output, model=args.model)
    return 0 if all(r.status == "ok" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
