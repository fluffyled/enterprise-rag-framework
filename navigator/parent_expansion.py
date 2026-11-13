"""Parent-Child Retrieval: восстановление полного родительского пункта (H1).

Каждый выбранный leaf-чанк заменяется полным текстом clause, который его
содержит (по source_span в координатах документа). Повторяющиеся clause
объединяются, порядок сохраняется, действует общий token budget.
"""

import json
import re
from pathlib import Path

from haystack import Document

STORE_PATH = Path(__file__).resolve().parent / ".." / "data" / "clauses" / "clauses.json"


def token_count_text(text):
    return len(re.findall(r"\w+|[^\w\s]", text or ""))


def load_clause_store(path=None):
    payload = json.loads(Path(path or STORE_PATH).read_text(encoding="utf-8"))
    return payload["documents"]


def _clauses_for_span(clauses, start, end):
    """Все clauses, пересекающиеся со спаном чанка (чанк может накрывать
    несколько пунктов из-за скользящего окна)."""
    return [clause for clause in clauses if clause["start"] < end and clause["end"] > start]


def _clause_for_position(clauses, position):
    """Самый специфичный (маленький) clause, содержащий позицию."""
    containing = [clause for clause in clauses if clause["start"] <= position < clause["end"]]
    if not containing:
        return None
    return min(containing, key=lambda clause: clause["end"] - clause["start"])


def expand_parents(documents, store, token_budget, related_clauses=False, **kwargs):
    expanded = []
    seen_clauses = set()
    used_tokens = 0

    def emit(clause, meta):
        nonlocal used_tokens
        if clause["clause_id"] in seen_clauses:
            return
        text = clause["full_text"]
        cost = token_count_text(text)
        if used_tokens + cost > token_budget:
            return
        used_tokens += cost
        seen_clauses.add(clause["clause_id"])
        new_meta = dict(meta)
        new_meta.update({
            "chunk_id": f"clause-{clause['clause_id']}",
            "clause_id": clause["clause_id"],
            "clause_number": clause["number"],
            "clause_title": clause["title"],
            "source_span": {"document_id": meta.get("document_id"), "start": clause["start"], "end": clause["end"]},
            "expanded_from_chunk": meta.get("chunk_id"),
        })
        expanded.append(Document(content=text, meta=new_meta))

    for document in documents:
        meta = document.meta
        sha = meta.get("sha256")
        source_span = meta.get("source_span") or {}
        entry = store.get(sha) if sha else None
        clauses = []
        if entry and source_span.get("start") is not None:
            span_end = source_span.get("end") or source_span["start"] + 1
            clauses = _clauses_for_span(entry["clauses"], source_span["start"], span_end)
        if not clauses:
            if used_tokens + token_count_text(document.content) <= token_budget:
                used_tokens += token_count_text(document.content)
                expanded.append(document)
            continue
        by_id = {clause["clause_id"]: clause for clause in entry["clauses"]}
        for clause in clauses:
            emit(clause, meta)
        if related_clauses:
            for clause in clauses:
                for reference_id in clause.get("references", []):
                    target = by_id.get(reference_id)
                    if target is not None:
                        emit(target, meta)
    return expanded
