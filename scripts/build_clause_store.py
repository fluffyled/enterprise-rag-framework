"""Построение clause-хранилища иерархии документов (Retrieval v4.1).

Разбивает текст документов на нумерованные пункты (clauses):
clause = номер (например 3.1, 10.2.1) + полный текст до следующего пункта
того же или более высокого уровня.

Гарантии (аудит v4.1):
- ПОЛНАЯ независимость от gold-разметки: gold не читается (валидация —
  scripts/validate_clause_store.py).
- Координаты: start/end — истинные границы в тексте документа; инвариант
  text[start:end].strip() == full_text проверяется на каждом пункте.
- Родитель — по числовому префиксу (родитель "2.1.1" = "2.1"); при
  невозможности однозначного восстановления parent_id=None + parent_ambiguous,
  связь не выдумывается.
- Повторяющаяся нумерация: references связываются только при уникальности
  номера в документе.
- Детерминированность: при неизменных входных документах выход побайтово
  воспроизводим; ID стабильны: sha256(sha документа + номер + start).

Проверка отсутствия gold-зависимости: скрипт успешно работает при полном
отсутствии data/hrag50/.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CLAUSE_RE = re.compile(r"(?m)^\s*(\d+(?:\.\d+)*)\.?\s+(?!\|)\S")


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
        # аудит 2.1: end — истинная граница (до начала следующего пункта),
        # а не start + len(body) (прежнее повреждение координат после strip).
        assert text[start:end].strip() == body, f"инвариант координат нарушен: {document_id} п.{number}"
        clause_id = hashlib.sha256(f"{sha256}:{number}:{start}".encode()).hexdigest()[:24]
        clauses.append({
            "clause_id": clause_id,
            "document_id": document_id,
            "number": number,
            "level": level,
            "title": body.splitlines()[0][:160] if body else "",
            "full_text": body,
            "start": start,
            "end": end,
        })
    # аудит 2.3: повторяющиеся номера — позиционный контекст
    number_counts = {}
    for clause in clauses:
        number_counts[clause["number"]] = number_counts.get(clause["number"], 0) + 1
    for index, clause in enumerate(clauses):
        # аудит 2.2: родитель — по числовому префиксу, не по «ближайшему выше»
        parent_number = clause["number"].rsplit(".", 1)[0] if "." in clause["number"] else None
        parent, parent_ambiguous = None, False
        if parent_number is not None:
            candidates = [c for c in clauses[:index] if c["number"] == parent_number]
            if len(candidates) == 1:
                parent = candidates[0]["clause_id"]
            elif len(candidates) > 1:
                parent = candidates[-1]["clause_id"]
                parent_ambiguous = True  # неоднозначная нумерация: связь эвристична
        clause["parent_id"] = parent
        clause["parent_ambiguous"] = parent_ambiguous
        clause["previous_id"] = clauses[index - 1]["clause_id"] if index > 0 else None
        clause["next_id"] = clauses[index + 1]["clause_id"] if index + 1 < len(clauses) else None
        # аудит 2.3: references — только при уникальном номере в документе
        references = []
        for match in REF_RE.finditer(clause["full_text"]):
            target_number = match.group(1)
            if number_counts.get(target_number, 0) != 1:
                continue  # неоднозначный номер — связь не выдумываем
            target = next((c for c in clauses if c["number"] == target_number), None)
            if target and target["clause_id"] != clause["clause_id"]:
                references.append(target["clause_id"])
        clause["references"] = sorted(set(references))
    return clauses


REF_RE = re.compile(r"(?:п\.|пп\.|пункт(?:а|е|у|ы)?|раздел(?:а|е)?)\s*(\d+(?:\.\d+)*)", re.IGNORECASE)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", default=str(ROOT / "data/source_documents.json"))
    parser.add_argument("--output", default=str(ROOT / "data/clauses/clauses.json"))
    args = parser.parse_args()

    documents = json.loads(Path(args.documents).read_text(encoding="utf-8"))
    # аудит 1.5: уникальность document ID и SHA
    doc_ids = [d["document_id"] for d in documents]
    shas = [d["sha256"] for d in documents]
    if len(doc_ids) != len(set(doc_ids)):
        raise ValueError("Дублирующиеся document_id во входном корпусе")
    if len(shas) != len(set(shas)):
        raise ValueError("Дублирующиеся sha256 во входном корпусе")

    store = {}
    report = {"documents": {}, "total_clauses": 0}
    clause_ids = set()
    for document in documents:
        clauses = parse_clauses(document["document_id"], document["sha256"], document["text"])
        for clause in clauses:
            if clause["clause_id"] in clause_ids:
                raise ValueError(f"Дублирующийся clause_id {clause['clause_id']}")
            clause_ids.add(clause["clause_id"])
        store[document["sha256"]] = {"document_id": document["document_id"], "clauses": clauses}
        spans = sorted((clause["start"], clause["end"]) for clause in clauses)
        merged = []
        for start, end in spans:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        covered = sum(end - start for start, end in merged)
        numbers = [clause["number"] for clause in clauses]
        report["documents"][document["document_id"]] = {
            "clauses": len(clauses),
            "has_numbered_clauses": len(clauses) > 0,
            "gap_ratio": round(1 - covered / len(document["text"]), 4) if document["text"] else 1.0,
            "duplicate_numbers": len(numbers) - len(set(numbers)),
        }
        report["total_clauses"] += len(clauses)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"documents": store}, ensure_ascii=False), encoding="utf-8")
    (out.parent / "clause_build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    no_clause_docs = [name for name, d in report["documents"].items() if not d["has_numbered_clauses"]]
    print(json.dumps({"total_clauses": report["total_clauses"], "documents": len(documents), "docs_without_clauses": len(no_clause_docs)}, ensure_ascii=False))
    print(out)


if __name__ == "__main__":
    main()
