#!/usr/bin/env python3
"""Generate fake receipt/invoice fixtures for receipts-to-ledger v0 tests.

Outputs to: fixtures/receipts/ (images + pdf + email + csv)
Golden CSV: fixtures/golden.csv

No real data. All vendors/amounts fictional. Renders receipt images with PIL,
PDFs with reportlab (fallback: text-only rendering via PIL if reportlab missing),
plus one pasted email (.txt) and one e-receipt CSV.
"""

import csv
import math
import os
import random
from datetime import date

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(os.path.dirname(__file__), "receipts")
os.makedirs(OUT_DIR, exist_ok=True)

random.seed(42)  # deterministic fixtures

FONT_DIRS = [
    "/System/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
]
_font_cache = {}


def load_font(name, size):
    key = (name, size)
    if key in _font_cache:
        return _font_cache[key]
    try:
        f = ImageFont.truetype(name, size)
    except OSError:
        f = ImageFont.load_default()
    _font_cache[key] = f
    return f


def any_font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Supplemental/Courier New.ttf",
    ] if not bold else [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except OSError:
            continue
    return ImageFont.load_default()


def jitter_font():
    return any_font(random.choice([13, 14, 15, 16]))


# ---------------------------------------------------------------- fixtures
# (vendor, address, date_iso, items [(desc, qty, unit_price)], tax_rate,
#  payment, template)
RECEIPTS = [
    ("Bay Area Office Supply", "1420 Grand Ave, Oakland CA", "2026-10-02",
     [("Copy paper 20lb", 4, 6.49), ("Staples", 1, 3.29), ("Ink cartridge", 1, 24.99)],
     0.0925, "VISA ****4821", "classic"),

    ("Castoro Cellars", "1312 N Bethel Rd, Templeton CA", "2026-10-14",
     [("Estate Zinfandel", 2, 22.00), ("Tasting fee", 2, 15.00)],
     0.0875, "MASTERCARD ****7710", "thermal"),

    ("Northbay Auto Repair", "881 Miller Ave, Mill Valley CA", "2026-09-21",
     [("Oil change synthetic", 1, 89.99), ("Cabin air filter", 1, 24.50), ("Labor", 1, 60.00)],
     0.0825, "AMEX ****1009", "classic"),

    ("Juniper Cafe", "500 Main St, Napa CA", "2026-10-30",
     [("Turkey sandwich", 1, 13.50), ("Drip coffee", 1, 3.75), ("Cookie", 1, 3.25)],
     0.0875, "DEBIT ****2231", "thermal"),

    ("Sierra Hardware", "77 River Rd, Ukiah CA", "2026-11-04",
     [("2in screws box", 2, 8.99), ("Wood glue", 1, 5.49), ("Sandpaper 120", 3, 2.19)],
     0.0875, "VISA ****4821", "classic"),

    ("Clear Lake Plumbing Co", "PO Box 219, Lakeport CA", "2026-10-08",
     [("Service call", 1, 95.00), ("Washer replacement", 1, 12.00)],
     0.0775, "CHECK #1042", "invoice"),

    ("Golden Gate Packers", "901 Marin St, San Francisco CA", "2026-11-11",
     [("Bubble wrap 100ft", 1, 18.99), ("Boxes medium x10", 1, 32.50), ("Packing tape", 2, 4.29)],
     0.0875, "VISA ****4821", "thermal"),

    ("Redwood Print & Copy", "210 Center St, Santa Rosa CA", "2026-10-19",
     [("Business cards 500", 1, 45.00), ("Lamination", 3, 2.00)],
     0.0875, "CASH", "classic"),

    ("Mendocino Mercantile", "12 Main St, Willits CA", "2026-09-28",
     [("Work gloves", 1, 14.99), ("LED bulb 2pk", 1, 9.49), ("Extension cord", 1, 21.99), ("Duct tape", 1, 6.29)],
     0.0825, "DEBIT ****2231", "thermal"),

    ("Pacific Web Hosting", "1 Market St Suite 400, San Francisco CA", "2026-10-01",
     [("Pro hosting plan (monthly)", 1, 29.00)],
     0.0, "ACH", "invoice"),

    ("Tahoe Ski & Board", "415 Lakeview Ave, South Lake Tahoe CA", "2026-11-15",
     [("Binding adjustment", 1, 35.00), ("Wax", 1, 25.00)],
     0.0775, "MASTERCARD ****7710", "classic"),

    ("Valley Green Landscaping Supply", "6300 Sonoma Hwy, Napa CA", "2026-10-25",
     [("Mulch 3cu yd", 1, 96.00), ("Delivery fee", 1, 40.00)],
     0.0825, "VISA ****4821", "invoice"),
]


def money(x):
    return f"${x:,.2f}"


def compute_total(items, tax_rate):
    subtotal = sum(q * p for _, q, p in items)
    tax = round(subtotal * tax_rate, 2)
    return subtotal, tax, round(subtotal + tax, 2)


# ------------------------------------------------------------- templates
def draw_classic(img, d, r, w, h):
    """Letterhead-ish white receipt, serif headers."""
    f_title = any_font(20, bold=True)
    f_addr = any_font(11)
    f_head = any_font(13, bold=True)
    f_body = jitter_font()
    f_right = any_font(14, bold=True)

    d.rectangle([0, 0, w - 1, h - 1], outline=(60, 60, 60), width=2)
    d.text((40, 34), r["vendor"], font=f_title, fill=(20, 20, 20))
    d.text((40, 62), r["address"], font=f_addr, fill=(70, 70, 70))
    d.line([40, 86, w - 40, 86], fill=(150, 150, 150), width=1)
    y = 104
    d.text((40, y), f"INVOICE / RECEIPT   #{random.randint(10000, 99999)}", font=f_head, fill=(30, 30, 30))
    y += 26
    d.text((40, y), f"Date: {r['date_display']}", font=f_body, fill=(30, 30, 30))
    d.text((w - 240, y), f"Paid by: {r['payment']}", font=f_body, fill=(30, 30, 30))
    y += 34
    d.text((40, y), "Description", font=f_head, fill=(30, 30, 30))
    d.text((w - 200, y), "Qty   Amount", font=f_head, fill=(30, 30, 30))
    y += 24
    for desc, qty, price in r["items"]:
        d.text((48, y), desc, font=f_body, fill=(40, 40, 40))
        d.text((w - 200, y), f"{qty} x {money(price)}", font=f_body, fill=(40, 40, 40))
        y += 22
    y += 10
    d.line([40, y, w - 40, y], fill=(150, 150, 150), width=1)
    y += 12
    subtotal, tax, total = r["totals"]
    d.text((40, y), f"Subtotal: {money(subtotal)}", font=f_body, fill=(40, 40, 40)); y += 20
    d.text((40, y), f"Tax ({r['tax_rate']*100:.3g}%): {money(tax)}", font=f_body, fill=(40, 40, 40)); y += 22
    d.text((40, y), f"TOTAL: {money(total)}", font=f_right, fill=(10, 10, 10))


def draw_thermal(img, d, r, w, h):
    """Narrow thermal-printer look, monospace, dashed cuts."""
    f_mono = any_font(13)
    f_big = any_font(16, bold=True)
    y = 26
    d.text((w // 2 - 110, y), r["vendor"].upper(), font=f_big, fill=(20, 20, 20)); y += 28
    d.text((20, y), r["address"], font=f_mono, fill=(50, 50, 50)); y += 22
    d.text((20, y), "-" * 34, font=f_mono, fill=(120, 120, 120)); y += 20
    d.text((20, y), f"{r['date_display']}   Reg {random.randint(1,4):02d}", font=f_mono, fill=(30, 30, 30)); y += 24
    for desc, qty, price in r["items"]:
        d.text((20, y), f"{qty} {desc[:24]}", font=f_mono, fill=(30, 30, 30))
        d.text((w - 110, y), money(price * qty).rjust(9), font=f_mono, fill=(30, 30, 30))
        y += 20
    y += 6
    d.text((20, y), "-" * 34, font=f_mono, fill=(120, 120, 120)); y += 20
    subtotal, tax, total = r["totals"]
    d.text((20, y), f"SUBTOTAL {money(subtotal)}".rjust(32), font=f_mono, fill=(30, 30, 30)); y += 20
    d.text((20, y), f"TAX {money(tax)}".rjust(32), font=f_mono, fill=(30, 30, 30)); y += 22
    d.text((20, y), f"TOTAL {money(total)}".rjust(32), font=f_big, fill=(10, 10, 10)); y += 30
    d.text((20, y), f"{r['payment']}".rjust(32), font=f_mono, fill=(50, 50, 50)); y += 22
    d.text((20, y), "-" * 34, font=f_mono, fill=(120, 120, 120)); y += 18
    d.text((20, y), "THANK YOU - COME AGAIN", font=f_mono, fill=(60, 60, 60))


def draw_invoice(img, d, r, w, h):
    """Clean invoice layout, email-ish."""
    f_title = any_font(18, bold=True)
    f_body = jitter_font()
    f_head = any_font(12, bold=True)
    y = 30
    d.text((40, y), r["vendor"], font=f_title, fill=(15, 60, 110)); y += 26
    d.text((40, y), r["address"], font=f_body, fill=(90, 90, 90)); y += 30
    d.text((40, y), f"INVOICE  INV-2026-{random.randint(1000,9999)}", font=f_head, fill=(30, 30, 30))
    d.text((w - 220, y), f"Due/Paid: {r['date_display']}", font=f_body, fill=(30, 30, 30)); y += 30
    d.line([40, y, w - 40, y], fill=(200, 200, 200), width=1); y += 14
    for desc, qty, price in r["items"]:
        d.text((48, y), f"{desc} (x{qty})", font=f_body, fill=(40, 40, 40))
        d.text((w - 140, y), f"{money(price * qty)}", font=f_body, fill=(40, 40, 40))
        y += 22
    y += 12
    subtotal, tax, total = r["totals"]
    d.text((40, y), f"Subtotal {money(subtotal)}   Tax {money(tax)}", font=f_body, fill=(40, 40, 40)); y += 22
    d.text((40, y), f"Amount paid: {money(total)}", font=f_head, fill=(10, 90, 40))
    d.text((w - 260, y), f"Method: {r['payment']}", font=f_body, fill=(30, 30, 30))


TEMPLATES = {"classic": draw_classic, "thermal": draw_thermal, "invoice": draw_invoice}

# golden rows: date, vendor, amount, tax, category, payment method
CATEGORY_MAP = {
    "Bay Area Office Supply": "Office supplies",
    "Castoro Cellars": "Meals & entertainment",
    "Northbay Auto Repair": "Auto",
    "Juniper Cafe": "Meals & entertainment",
    "Sierra Hardware": "Supplies",
    "Clear Lake Plumbing Co": "Facilities",
    "Golden Gate Packers": "Shipping & packing",
    "Redwood Print & Copy": "Office supplies",
    "Mendocino Mercantile": "Supplies",
    "Pacific Web Hosting": "Software & services",
    "Tahoe Ski & Board": "Meals & entertainment",
    "Valley Green Landscaping Supply": "Facilities",
}


def render_image_receipt(r, idx, angle, noise):
    w = random.choice([640, 700, 760])
    h = random.choice([420, 460, 500])
    img = Image.new("RGB", (w, h), (random.randint(244, 252),) * 3)
    d = ImageDraw.Draw(img)
    TEMPLATES[r["template"]](img, d, r, w, h)
    if angle:
        img = img.rotate(angle, expand=True, fillcolor=(248, 248, 248), resample=Image.BICUBIC)
    if noise:
        px = img.load()
        for _ in range(int(img.width * img.height * 0.01)):
            x, y = random.randrange(img.width), random.randrange(img.height)
            v = random.randint(180, 230)
            px[x, y] = (v, v, v)
    img.save(os.path.join(OUT_DIR, f"{idx:02d}_{r['slug']}.png"), quality=88)


def write_pdf_receipt(r, idx):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas as pdfcanvas
    except ImportError:
        # fallback: render as image instead
        render_image_receipt(r, idx, 0, False)
        return False
    from reportlab.lib.units import inch

    path = os.path.join(OUT_DIR, f"{idx:02d}_{r['slug']}.pdf")
    c = pdfcanvas.Canvas(path, pagesize=letter)
    width, _ = letter
    y = 10 * inch - 1.2 * inch
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, r["vendor"]); y -= 18
    c.setFont("Helvetica", 9)
    c.drawString(72, y, r["address"]); y -= 26
    c.setFont("Helvetica-Bold", 11)
    c.drawString(72, y, f"RECEIPT #{random.randint(10000, 99999)}"); y -= 16
    c.setFont("Helvetica", 10)
    c.drawString(72, y, f"Date: {r['date_display']}    Paid by: {r['payment']}"); y -= 24
    for desc, qty, price in r["items"]:
        c.drawString(80, y, desc)
        c.drawRightString(width - 80, y, f"{qty} x {money(price)}")
        y -= 16
    y -= 10
    subtotal, tax, total = r["totals"]
    c.drawString(72, y, f"Subtotal: {money(subtotal)}   Tax: {money(tax)}"); y -= 16
    c.setFont("Helvetica-Bold", 12)
    c.drawString(72, y, f"TOTAL: {money(total)}")
    c.save()
    return True


def main():
    golden_rows = []
    pdf_used = 0
    for i, (vendor, address, date_iso, items, tax_rate, payment, template) in enumerate(RECEIPTS, start=1):
        subtotal, tax, total = compute_total(items, tax_rate)
        y, m, dd = date_iso.split("-")
        date_display = f"{int(m)}/{int(dd)}/{y}"
        r = {
            "vendor": vendor, "address": address, "date_iso": date_iso,
            "date_display": date_display, "items": items, "tax_rate": tax_rate,
            "payment": payment, "template": template,
            "totals": (subtotal, tax, total),
            "slug": vendor.lower().replace(" ", "-").replace("&", "and")[:28],
        }
        style = i % 4
        if i == 7:  # Golden Gate Packers -> e-receipt CSV only (no image)
            pass
        elif i == 10:  # Pacific Web Hosting -> pasted email receipt only
            pass
        elif i in (3, 9) and pdf_used < 2:  # exactly 2 PDFs
            pdf_used += 1 if write_pdf_receipt(r, i) else 0
        elif style == 1:
            render_image_receipt(r, i, angle=random.uniform(-4, 4), noise=True)
        elif style == 2:
            render_image_receipt(r, i, angle=random.uniform(-2, 2), noise=False)
        else:
            render_image_receipt(r, i, angle=0, noise=False)
        golden_rows.append({
            "date": date_iso, "vendor": vendor, "amount": f"{total:.2f}",
            "tax": f"{tax:.2f}", "category": CATEGORY_MAP[vendor],
            "payment_method": payment,
        })

    # e-receipt CSV (replaces the image for i=7 Golden Gate Packers)
    csv_vendor = "Golden Gate Packers"
    with open(os.path.join(OUT_DIR, "07_ereceipt.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_date", "merchant", "line", "qty", "unit_price", "tax_collected", "total_charged", "tender"])
        w.writerow(["2026-11-11", csv_vendor, "Bubble wrap 100ft", 1, 18.99, "", "", ""])
        w.writerow(["2026-11-11", csv_vendor, "Boxes medium x10", 1, 32.50, "", "", ""])
        w.writerow(["2026-11-11", csv_vendor, "Packing tape", 2, 4.29, "", "", ""])
        subtotal, tax, total = compute_total([x for x in RECEIPTS[6][3]], RECEIPTS[6][4])
        w.writerow(["2026-11-11", csv_vendor, "", "", "", tax, total, "VISA ****4821"])

    # pasted email receipt (replaces the image for i=11 Pacific Web Hosting)
    email_receipt = f"""From: billing@pacificwebhosting.example
Subject: Your receipt — October 2026

Thanks for your payment!

Date: 10/01/2026
Amount charged: $29.00
Payment method: ACH
Description: Pro hosting plan (monthly)
Invoice ID: INV-2026-5521
"""
    with open(os.path.join(OUT_DIR, "10_email_receipt.txt"), "w") as f:
        f.write(email_receipt)

    with open(os.path.join(os.path.dirname(OUT_DIR), "golden.csv"), "w", newline="") as f:
        wtr = csv.DictWriter(f, fieldnames=["date", "vendor", "amount", "tax", "category", "payment_method"])
        wtr.writeheader()
        for row in golden_rows:
            wtr.writerow(row)

    print(f"fixtures: {len(os.listdir(OUT_DIR))} files in {OUT_DIR}")
    print("golden.csv written")
    for row in golden_rows:
        print(f"  {row['date']}  {row['vendor'][:32]:<32} {row['amount']:>8}  {row['category']}")


if __name__ == "__main__":
    main()
