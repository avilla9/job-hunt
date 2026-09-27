import re


def offer_salary(text):
    if not text:
        return None
    best = None
    money = r"(?:\$|USD|US\$|€|EUR)\s?(\d{1,3}(?:[.,]\d{3})+|\d+(?:\.\d+)?)\s?([kK])?|(\d{1,3}(?:[.,]\d{3})+|\d+(?:\.\d+)?)\s?([kK])?\s?(?:USD|EUR|€|\$)"
    for m in re.finditer(money, text):
        raw, k = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        value = float(re.sub(r"[.,](?=\d{3}\b)", "", raw).replace(",", "."))
        if k:
            value *= 1000
        window = text[m.end():m.end() + 25].lower()
        if re.search(r"/\s?h|per hour|hourly|an hour", window):
            value *= 2080
        elif re.search(r"/\s?mo|per month|monthly|a month|mensual", window) or 1000 <= value < 20000:
            value *= 12
        if 10000 <= value <= 1000000:
            best = max(best or 0, value)
    return int(best) if best else None
