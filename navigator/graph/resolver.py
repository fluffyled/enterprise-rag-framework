import re


ORDER_PATTERN = re.compile(r"(?:приказ[а-я]*|распоряжени[а-я]*)[^\n]{0,100}?(?:от\s+(\d{2}\.\d{2}\.\d{4}))?[^\n]{0,30}?[№N]\s*(\d+(?:-\d+)?)", re.IGNORECASE)


def normalize_number(value):
    return re.sub(r"\s+", "", value).upper().replace("N", "№").lstrip("№")


def document_signature(document):
    text = document["text"][:2500]
    filename = document["document_id"]
    number = re.search(r"(?:№|N)\s*(\d+(?:-\d+)?)", filename, re.IGNORECASE)
    date = re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", filename)
    number_value = number.group(1) if number else None
    date_value = date.group() if date else None
    if not number_value:
        match = ORDER_PATTERN.search(text)
        if match:
            number_value = match.group(2)
            date_value = match.group(1)
    return {"number": normalize_number(number_value) if number_value else None, "date": date_value}


def resolve_reference(reference, catalog):
    candidates = catalog.get(normalize_number(reference["number"]), [])
    if not candidates:
        return None
    if reference.get("date"):
        exact = [candidate for candidate in candidates if candidate["date"] == reference["date"]]
        if exact:
            candidates = exact
    if len(candidates) != 1:
        return None
    return candidates[0]
