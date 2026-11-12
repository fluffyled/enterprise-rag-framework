"""Manual approved topics; classifications are never inferred as regulatory facts."""
import csv
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

def topics():
    path = DATA / "topics.json"
    if not path.exists(): path = ROOT / "config/topics.json"
    return validate_topics(json.loads(path.read_text(encoding="utf-8")))

def validate_topics(payload):
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("topics"), list):
        raise ValueError("Нужен объект schema_version=1, topics=[{id, name}]")
    result = {}
    for item in payload["topics"]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip() or not isinstance(item.get("name"), str) or not item["name"].strip(): raise ValueError("Некорректная тема")
        if item["id"] in result: raise ValueError("Повторяется ID темы")
        result[item["id"]] = item["name"]
    return result

def read_assignments(text, allowed_topics):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if reader.fieldnames != ["document_id", "topic_ids"]: raise ValueError("CSV: document_id,topic_ids; темы разделяются точкой с запятой")
    result = {}
    for row in reader:
        doc = (row.get("document_id") or "").strip()
        ids = tuple(x.strip() for x in (row.get("topic_ids") or "").split(";") if x.strip())
        if not doc or doc in result: raise ValueError("Пустой или повторный document_id")
        if set(ids) - set(allowed_topics): raise ValueError("В CSV есть неизвестные темы")
        result[doc] = ids
    return result

def assignments():
    path = DATA / "document_topics.csv"
    return read_assignments(path.read_text(encoding="utf-8"), topics()) if path.exists() else {}

def csv_text(rows):
    stream = io.StringIO(); writer = csv.writer(stream); writer.writerow(["document_id", "topic_ids"])
    for doc, ids in rows.items(): writer.writerow([doc, ";".join(ids)])
    return stream.getvalue()
