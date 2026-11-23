"""Render the first page of a PDF to PNG bytes so it can go through the vision path."""

import fitz  # PyMuPDF


def first_page_png(pdf_path: str, zoom: float = 2.0) -> bytes:
    """Render page 1 of a PDF as PNG bytes at the given zoom (2.0 = 144 dpi)."""
    doc = fitz.open(pdf_path)
    try:
        page = doc[0]
        matrix = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        return pix.tobytes("png")
    finally:
        doc.close()
