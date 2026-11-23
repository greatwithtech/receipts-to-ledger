"""Rule-based expense categories.

v0 uses a keyword list over the vendor name and line item descriptions.
It is transparent and free; it will not match every business's chart of
accounts, so treat the category column as a starting point.
"""

# (category, keywords) checked in order; first hit wins.
RULES = [
    ("Auto", ["auto repair", "auto", "oil change", "tire", "smog", "transmission", "car wash", "parking"]),
    ("Software & services", ["hosting", "software", "saas", "subscription", "domain", "cloud", "web services"]),
    ("Shipping & packing", ["packers", "shipping", "postage", "bubble wrap", "packing", "freight", "courier"]),
    ("Facilities", ["plumbing", "plumber", "landscap", "electric", "hvac", "janitorial", "service call", "mulch", "delivery fee", "repair"]),
    ("Office supplies", ["office supply", "office supplies", "print", "copy", "copy paper", "ink", "staples", "business card", "lamination"]),
    ("Meals & entertainment", ["cafe", "coffee", "restaurant", "sandwich", "deli", "bakery", "winery", "cellars", "tasting", "catering", "ski", "board"]),
    ("Supplies", ["hardware", "gloves", "bulb", "cord", "tape", "screws", "sandpaper", "glue", "tools", "mercantile", "lumber"]),
]


def categorize(vendor: str, description: str = "", line_items=None) -> str:
    """Return a category for a row, or 'Other' when no rule matches."""
    haystack_parts = [vendor or ""]
    if description:
        haystack_parts.append(description)
    for item in line_items or []:
        desc = item.get("description") if isinstance(item, dict) else getattr(item, "description", "")
        if desc:
            haystack_parts.append(desc)
    haystack = " ".join(haystack_parts).lower()

    for category, keywords in RULES:
        for keyword in keywords:
            if keyword in haystack:
                return category
    return "Other"
