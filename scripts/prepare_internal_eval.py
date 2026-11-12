import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.settings import DATA


def resolve_group(group, documents):
    if isinstance(group, dict) and "alternatives" in group:
        alternatives = group["alternatives"]
    else:
        alternatives = [group]
    resolved = []
    for alternative in alternatives:
        index, anchor = alternative
        document = documents[index]
        count = document["text"].count(anchor)
        if not count:
            raise ValueError(f"Якорь не найден: document={index}, anchor={anchor!r}")
        offset = 0
        for _ in range(count):
            start = document["text"].index(anchor, offset)
            resolved.append({"document_id": document["document_id"], "start": start, "end": start + len(anchor), "text": anchor})
            offset = start + len(anchor)
    return {"id": "", "requirement": " / ".join(item["text"] for item in resolved), "alternatives": resolved}


def main():
    source = json.loads((DATA / "retrieval_eval_source.json").read_text(encoding="utf-8"))
    documents = json.loads((DATA / "source_documents.json").read_text(encoding="utf-8"))
    queries = []
    for row in source:
        groups = [resolve_group(group, documents) for group in row["g"]]
        for index, group in enumerate(groups, 1):
            group["id"] = f"{row['id']}-requirement-{index}"
        gold_documents = sorted({span["document_id"] for group in groups for span in group["alternatives"]})
        answerable = row.get("answerable", True)
        if answerable and not groups:
            raise ValueError(f"Нет evidence: {row['id']}")
        if not answerable and groups:
            raise ValueError(f"Неотвечаемый вопрос имеет evidence: {row['id']}")
        queries.append({
            "id": row["id"], "question": row["q"], "question_type": row["type"], "answerable": answerable,
            "gold_document_ids": gold_documents, "evidence_groups": groups,
            "semantic_requirements": [group["requirement"] for group in groups],
            "family": row["family"], "split": row["split"], "annotation": {"method": "manual_anchor_review", "review_status": "single_annotator"},
        })
    if not 50 <= len(queries) <= 80:
        raise ValueError("Нужно 50–80 вопросов")
    if len({row["id"] for row in queries}) != len(queries):
        raise ValueError("Дубликаты ID")
    families = {}
    for row in queries:
        families.setdefault(row["family"], set()).add(row["split"])
    if any(len(splits) != 1 for splits in families.values()):
        raise ValueError("Семейство документов попало в dev и holdout")
    for split in ("all", "dev", "holdout"):
        selected = queries if split == "all" else [row for row in queries if row["split"] == split]
        payload = {"schema_version": 1, "private": True, "split": split, "queries": selected}
        (DATA / f"retrieval_eval_{split}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"questions": len(queries), "splits": dict(Counter(row["split"] for row in queries)), "types": dict(Counter(row["question_type"] for row in queries)), "families": len(families)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
