"""Offline-валидация Clause Store против gold-разметки complex50.

Выделена из build_clause_store.py (аудит v4.1, этап 1): построение store не
читает gold; эта проверка запускается отдельно и только для evaluation.
Проверяет: каждая gold-цитата находится внутри clause с номером из разметки.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from navigator.parent_expansion import clause_entry, load_clause_store


def norm_with_map(text):
    parts = []
    offsets = []
    index = 0
    length = len(text)
    while index < length:
        if text[index].isspace():
            while index < length and text[index].isspace():
                index += 1
            if parts:
                parts.append(" ")
                offsets.append(index - 1)
        else:
            parts.append(text[index])
            offsets.append(index)
            index += 1
    return "".join(parts), offsets


def find_in_original(document_text, needle):
    norm_text, offsets = norm_with_map(document_text)
    position = norm_text.find(needle)
    if position < 0:
        return None
    last = position + len(needle) - 1
    return offsets[position], offsets[last] + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", default=str(ROOT / "data/clauses/clauses.json"))
    parser.add_argument("--documents", default=str(ROOT / "data/source_documents.json"))
    parser.add_argument("--gold", default=str(ROOT / "data/hrag50/hierarchical_complex_qa_50.jsonl"))
    args = parser.parse_args()

    store = load_clause_store(args.store)
    documents = json.loads(Path(args.documents).read_text(encoding="utf-8"))
    gold = [json.loads(line) for line in Path(args.gold).read_text(encoding="utf-8").splitlines() if line.strip()]

    by_name = {d["document_id"]: d for d in documents}
    misses = []
    for row in gold:
        for evidence in row["gold_evidence"]:
            document = by_name.get(evidence["document_filename"])
            if not document:
                misses.append((evidence["evidence_id"], "no document"))
                continue
            entry = clause_entry(store, document["document_id"], document["sha256"])
            clauses = entry["clauses"] if entry else []
            needle = re.sub(r"\s+", " ", evidence["evidence_needle"]).strip()
            span = find_in_original(document["text"], needle)
            if span is None:
                misses.append((evidence["evidence_id"], "needle not in document text"))
                continue
            start, end = span
            section_match = re.search(r"(\d+(?:\.\d+)*)", evidence["location"].get("section", ""))
            if not section_match:
                continue
            number = section_match.group(1)
            if not any(c["number"] == number and c["start"] <= start and end <= c["end"] for c in clauses):
                misses.append((evidence["evidence_id"], f"clause {number} does not contain needle"))
    total = sum(len(row["gold_evidence"]) for row in gold)
    result = {"gold_evidence_total": total, "gold_evidence_missed": misses, "covered": total - len(misses)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not misses else 1


if __name__ == "__main__":
    raise SystemExit(main())
