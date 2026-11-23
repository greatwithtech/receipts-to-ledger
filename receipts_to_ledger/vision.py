"""Vision extraction: send a receipt image to the OpenAI API and get structured data back."""

import base64
import os
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

DEFAULT_MODEL = os.environ.get("RECEIPTS_TO_LEDGER_MODEL", "gpt-4o-mini")

EXTRACTION_PROMPT = """You are a careful data entry clerk preparing records for an accountant.
Extract the following fields from this receipt or invoice image.

Rules:
- date: the transaction date, converted to ISO format (yyyy-mm-dd). Convert whatever
  format is printed, such as 10/2/2026 or Oct 2, 2026, into 2026-10-02.
- vendor: the business name exactly as printed on the document.
- line_items: every purchased item, with its description, quantity, and unit price.
  If quantity is not printed, use 1. If unit price is not printed, use the line total.
- tax: the sales tax charged. Use 0 if no tax is shown.
- total: the final amount paid, including tax.
- payment_method: how the bill was paid, exactly as printed, for example
  "VISA ****4821", "CASH", "AMEX ****1009", "CHECK #1042", "ACH".
  Copy the payment line character for character: card networks are uppercase
  and masked numbers use exactly the number of asterisk characters printed.
  Use an empty string only if nothing is printed about payment.
- currency: the 3-letter currency code. Use "USD" if not printed.

Read carefully. If a character is hard to read, use the most likely reading."""


class LineItem(BaseModel):
    description: str = Field(description="Item description as printed")
    quantity: float = Field(default=1, description="Quantity purchased")
    unit_price: float = Field(description="Price per unit in the receipt currency")


class ReceiptData(BaseModel):
    date: str = Field(description="Transaction date in ISO format yyyy-mm-dd")
    vendor: str = Field(description="Business name as printed")
    line_items: List[LineItem] = Field(default_factory=list)
    tax: float = Field(default=0, description="Sales tax charged")
    total: float = Field(description="Final amount paid including tax")
    payment_method: str = Field(default="", description="Payment method as printed")
    currency: str = Field(default="USD", description="3-letter currency code")


class MissingKeyError(RuntimeError):
    pass


def get_client():
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise MissingKeyError(
            "OPENAI_API_KEY is not set. Export it first, for example:\n"
            "  export OPENAI_API_KEY=sk-...  (get a key at platform.openai.com)"
        )
    from openai import OpenAI

    return OpenAI()


def extract_from_image_bytes(image_bytes: bytes, mime: str, client=None, model: str = None) -> ReceiptData:
    """Run vision extraction on raw image bytes."""
    client = client or get_client()
    model = model or DEFAULT_MODEL
    image_bytes = preprocess_image(image_bytes)
    b64 = base64.b64encode(image_bytes).decode("ascii")
    response = client.chat.completions.parse(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64}"},
                    },
                ],
            }
        ],
        response_format=ReceiptData,
    )
    data = response.choices[0].message.parsed
    if data is None:
        raise ValueError("model did not return parsed data")
    return data


def normalize_date(raw: str) -> str:
    """Best-effort normalization of a printed date to ISO yyyy-mm-dd. Returns input if unparseable."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    for fmt in (
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw


def preprocess_image(image_bytes: bytes, min_width: int = 1200) -> bytes:
    """Upscale small images so fine print (masked card numbers, dates) survives
    vision encoding. Larger is left untouched to control token cost."""
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes))
        if img.width >= min_width:
            return image_bytes
        factor = min_width / img.width
        img = img.resize((int(img.width * factor), int(img.height * factor)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return image_bytes  # if PIL is unavailable, send the original


def extract_from_image_path(path: str, client=None, model: str = None) -> ReceiptData:
    mime = "image/jpeg" if str(path).lower().endswith((".jpg", ".jpeg")) else "image/png"
    with open(path, "rb") as f:
        image_bytes = f.read()
    data = extract_from_image_bytes(image_bytes, mime, client=client, model=model)
    data.date = normalize_date(data.date)
    return data
