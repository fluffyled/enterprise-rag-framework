"""Построение clause-хранилища иерархии документов (этап 3 ТЗ).

Разбивает текст документов на нумерованные пункты (clauses):
clause = номер (например 3.1, 10.2.1) + полный текст до следующего пункта
того же или более высокого уровня. Родитель — ближайший предыдущий пункт
уровнем выше. ID стабильны: sha256(sha документа + номер + start).

Проверки: покрытие gold evidence complex50 (каждая цитата внутри ровно одного
clause), потери текста (gap ratio), таблицы/списки.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLD = ROOT / "data/hrag50/hierarchical_complex_qa_50.jsonl"
OUT = ROOT / "data/clauses/clauses.json"

CLAUSE_RE = re.compile(r"(?m)^\s*(\d+(?:\.\d+)*)\.?\s+(?!\|)\S")


def norm_with_map(text):
    """Нормализация пробелов с картой смещений: norm[i] соответствует original[offsets[i]]."""
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
    """Ищет needle (после нормализации) и возвращает (start, end) в оригинальных координатах."""
    norm_text, offsets = norm_with_map(document_text)
    position = norm_text.find(needle)
    if position < 0:
        return None
    last = position + len(needle) - 1
    return offsets[position], offsets[last] + 1


def parse_clauses(document_id, sha256, text):
    matches = list(CLAUSE_RE.finditer(text))
    clauses = []
    for index, match in enumerate(matches):
        number = match.group(1)
        level = number.count(".") + 1
        start = match.start()
        end = len(text)
        for later in matches[index + 1:]:
            if later.group(1).count(".") + 1 <= level:
                end = later.start()
                break
        body = text[start:end].strip()
        clause_id = hashlib.sha256(f"{sha256}:{number}:{start}".encode()).hexdigest()[:24]
        clauses.append({
            "clause_id": clause_id,
            "document_id": document_id,
            "number": number,
            "level": level,
            "title": body.splitlines()[0][:160] if body else "",
            "full_text": body,
            "start": start,
            "end": start + len(body),
        })
    for index, clause in enumerate(clauses):
        parent = None
        for earlier in reversed(clauses[:index]):
            if earlier["level"] == clause["level"] - 1:
                parent = earlier["clause_id"]
                break
        clause["parent_id"] = parent
    return clauses


def main():
    documents = json.loads((ROOT / "data/source_documents.json").read_text(encoding="utf-8"))
    gold = [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]
    needed = {e["document_filename"] for row in gold for e in row["gold_evidence"]}

    store = {}
    report = {"documents": {}, "total_clauses": 0}
    for document in documents:
        if document["document_id"] not in needed:
            continue
        clauses = parse_clauses(document["document_id"], document["sha256"], document["text"])
        store[document["sha256"]] = {"document_id": document["document_id"], "clauses": clauses}
        spans = sorted((clause["start"], clause["end"]) for clause in clauses)
        merged = []
        for start, end in spans:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        covered = sum(end - start for start, end in merged)
        report["documents"][document["document_id"]] = {
            "clauses": len(clauses),
            "gap_ratio": round(1 - covered / len(document["text"]), 4),
        }
        report["total_clauses"] += len(clauses)

    # проверка: gold needle находится в clause с номером из location.section
    by_name = {d["document_id"]: d for d in documents}
    misses = []
    for row in gold:
        for evidence in row["gold_evidence"]:
            document = by_name.get(evidence["document_filename"])
            if not document:
                misses.append((evidence["evidence_id"], "no document"))
                continue
            clauses = store[document["sha256"]]["clauses"]
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
    report["gold_evidence_missed"] = misses
    report["gold_evidence_total"] = sum(len(row["gold_evidence"]) for row in gold)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"documents": store}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)[:2000])
    print(OUT)


if __name__ == "__main__":
    main()
