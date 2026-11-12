import json
from pathlib import Path

from .common import chunks_from_documents, download_and_extract_zip


URL = "https://doc2dial.github.io/multidoc2dial/file/multidoc2dial.zip"


def parse_multidoc2dial(documents, dialogues, split="validation", query_limit=None, document_limit=None, include_history=True):
    document_rows = []
    for domain, rows in documents["doc_data"].items():
        for document_id, document in rows.items():
            document_rows.append({
                "document_id": document_id,
                "title": document["title"],
                "text": document["doc_text"],
                "domain": domain,
                "spans": document["spans"],
            })
    document_rows.sort(key=lambda row: row["document_id"])
    if document_limit is not None:
        document_rows = document_rows[:document_limit]
    by_id = {row["document_id"]: row for row in document_rows}
    queries = []
    skipped_missing_documents = 0
    for domain, rows in dialogues["dial_data"].items():
        for dialogue in rows:
            history = []
            turns = dialogue["turns"]
            for index, turn in enumerate(turns):
                if turn["role"] != "user":
                    continue
                target = turns[index + 1] if index + 1 < len(turns) else None
                if not target or target["role"] != "agent" or target["da"] == "respond_no_solution" or not target["references"]:
                    history.append(f"{turn['role']}: {turn['utterance']}")
                    continue
                references = target["references"]
                if any(reference["doc_id"] not in by_id for reference in references):
                    skipped_missing_documents += 1
                    history.append(f"user: {turn['utterance']}")
                    continue
                question = turn["utterance"].replace("\n", " ").replace("\t", " ").strip()
                if include_history and history:
                    question = question + "\nDialogue history:\n" + "\n".join(history)
                groups = []
                by_document = {}
                for reference in references:
                    by_document.setdefault(reference["doc_id"], []).append(reference["id_sp"])
                for document_id, span_ids in by_document.items():
                    document = by_id[document_id]
                    spans = document["spans"]
                    selected = [spans[span_id] if isinstance(spans, dict) else next(item for item in spans if item["id_sp"] == span_id) for span_id in span_ids]
                    start = min(int(span["start_sp"]) for span in selected)
                    end = max(int(span["end_sp"]) for span in selected)
                    groups.append({
                        "id": f"grounding-{document_id}",
                        "alternatives": [{"document_id": document_id, "start": start, "end": end, "text": document["text"][start:end]}],
                    })
                queries.append({
                    "id": f"{dialogue['dial_id']}_{turn['turn_id']}",
                    "question": question,
                    "answerable": True,
                    "question_type": "dialogue_grounding",
                    "gold_document_ids": sorted(by_document),
                    "evidence_groups": groups,
                    "domain": domain,
                    "split": split,
                })
                history.append(f"user: {turn['utterance']}")
                history.append(f"agent: {target['utterance']}")
                if query_limit is not None and len(queries) >= query_limit:
                    return _dataset(document_rows, queries, skipped_missing_documents, include_history)
    return _dataset(document_rows, queries, skipped_missing_documents, include_history)


def _dataset(documents, queries, skipped, include_history):
    for document in documents:
        document.pop("spans", None)
    return {
        "name": "multidoc2dial",
        "language": "en",
        "documents": documents,
        "queries": queries,
        "chunks": chunks_from_documents(documents),
        "metadata": {"official": False, "history_included": include_history, "target_agent_answer_in_query": False, "skipped_missing_documents": skipped},
    }


def load_multidoc2dial(split="validation", query_limit=None, document_limit=None, include_history=True, data_dir=None):
    if data_dir:
        root = Path(data_dir)
    else:
        root = download_and_extract_zip(URL, "multidoc2dial") / "multidoc2dial"
    documents = json.loads((root / "multidoc2dial_doc.json").read_text(encoding="utf-8"))
    dialogues = json.loads((root / f"multidoc2dial_dial_{split}.json").read_text(encoding="utf-8"))
    return parse_multidoc2dial(documents, dialogues, split, query_limit, document_limit, include_history)
