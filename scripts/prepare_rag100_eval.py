"""Адаптер rag100 → внутренний формат end-to-end оценки.

Каждый отвечаемый вопрос становится одной evidence-группой: альтернатива —
needle-фрагмент с точными start/end в тексте исходного документа
(ищется в data/source_documents.json по имени файла). Неотвечаемые вопросы
сохраняются с answerable=false для оценки abstention.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    gold = [json.loads(line) for line in (ROOT / "data/rag100/rag_gold_qa.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    documents = json.loads((ROOT / "data/source_documents.json").read_text(encoding="utf-8"))
    by_name = {document["document_id"]: document for document in documents}

    queries = []
    skipped = []
    for row in gold:
        if not row["answerable"]:
            queries.append({
                "id": row["id"], "question": row["question"], "question_type": "unanswerable",
                "answerable": False, "gold_document_ids": [], "evidence_groups": [],
                "semantic_requirements": [], "family": row.get("category"), "split": row["split"],
                "annotation": {"method": "rag100_external", "review_status": "external_single_annotator"},
            })
            continue
        document = by_name.get(row["gold_document_filename"])
        if document is None:
            skipped.append(row["id"])
            continue
        needle = row["evidence_needle"]
        start = document["text"].find(needle)
        if start < 0:
            import re

            pattern = r"\s+".join(re.escape(token) for token in needle.split())
            match = re.search(pattern, document["text"])
            start = match.start() if match else -1
        if start < 0:
            skipped.append(row["id"])
            continue
        end = start + len(needle) if document["text"].startswith(needle, start) else (match.end() if start >= 0 else start + len(needle))
        span = {"document_id": document["document_id"], "start": start, "end": end, "text": document["text"][start:end]}
        group = {"id": f"{row['id']}-requirement-1", "requirement": needle, "alternatives": [span]}
        queries.append({
            "id": row["id"], "question": row["question"], "question_type": row.get("difficulty", "simple_fact"),
            "answerable": True, "gold_document_ids": sorted(set(row["gold_document_ids"])), "evidence_groups": [group],
            "semantic_requirements": [needle], "family": row.get("category"), "split": row["split"],
            "annotation": {"method": "rag100_external", "review_status": "external_single_annotator"},
            "reference_answer": row.get("reference_answer"),
        })
    output = ROOT / "data/rag100/rag100_eval.json"
    output.write_text(json.dumps({"schema_version": 1, "private": True, "split": "rag100", "queries": queries}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"queries: {len(queries)}, skipped: {skipped}")
    print(output)


if __name__ == "__main__":
    main()
