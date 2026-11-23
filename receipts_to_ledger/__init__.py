"""receipts-to-ledger: turn a folder of receipts and invoices into one ledger CSV."""

from .pipeline import process_folder

__version__ = "0.1.0"

__all__ = ["process_folder"]
