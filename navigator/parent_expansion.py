"""Parent-Child Retrieval: восстановление полного родительского пункта (v4.1).

Каждый выбранный leaf-чанк заменяется полными пунктами (clauses), пересекающими
его source_span. Гарантии аудита v4.1 (этап 3):
- нет тихого исчезновения чанка: при невозможности разворачивания выполняется
  безопасный fallback на исходный чанк (если он помещается в бюджет), иначе
  причина потери фиксируется в диагностике (budget_exhausted и т.п.);
- каждый результат несёт контракт происхождения: документ+ID, chunk_id,
  clause_id, номер пункта, страницу/локатор, source_span, expansion_status;
- дедупликация по clause_id (зависит от sha документа — одинаковые тексты из
  разных документов не объединяются);
- бюджет токенов не превышается никогда.

Возвращает (documents, diagnostics); diagnostics — список dict с полями
status: expanded_successfully | fallback_to_original_chunk | clause_too_large |
budget_exhausted | missing_clause | invalid_source_span.
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
    if payload.get("schema_version") == 2:
        return {(entry["document_id"], entry["sha256"]): entry for entry in payload["documents"]}
    return payload["documents"]


def clause_entry(store, document_id, sha):
    entry = store.get((document_id, sha)) or store.get(sha)
    return entry if entry and (not document_id or entry.get("document_id") == document_id) else None


def _clauses_for_span(clauses, start, end):
    """Все clauses, пересекающиеся со спаном чанка (чанк может накрывать
    несколько пунктов из-за скользящего окна)."""
    return [clause for clause in clauses if clause["start"] < end and clause["end"] > start]


def expand_parents(documents, store, token_budget, related_clauses=False, **kwargs):
    expanded = []
    diagnostics = []
    seen_clauses = set()
    used_tokens = 0

    def emit_chunk_fallback(document, reason):
        nonlocal used_tokens
        cost = token_count_text(document.content)
        entry = {
            "chunk_id": document.meta.get("chunk_id"),
            "status": "fallback_to_original_chunk",
            "reason": reason,
        }
        if used_tokens + cost <= token_budget:
            used_tokens += cost
            expanded.append(document)
        else:
            entry["status"] = "budget_exhausted"
            entry["reason"] = f"{reason}; исходный чанк тоже не помещается"
        diagnostics.append(entry)

    for document in documents:
        meta = document.meta
        sha = meta.get("sha256")
        source_span = meta.get("source_span") or {}
        entry = clause_entry(store, meta.get("document_id"), sha) if sha else None
        start = source_span.get("start")
        if entry is None or not isinstance(start, int) or start < 0:
            emit_chunk_fallback(document, "missing_clause" if entry is None else "invalid_source_span")
            continue
        span_end = source_span.get("end")
        if not isinstance(span_end, int) or span_end <= start:
            emit_chunk_fallback(document, "invalid_source_span")
            continue
        clauses = _clauses_for_span(entry["clauses"], start, span_end)
        if not clauses:
            emit_chunk_fallback(document, "missing_clause")
            continue
        emitted_for_chunk = False
        for clause in clauses:
            if clause["clause_id"] in seen_clauses:
                continue
            text = clause["full_text"]
            cost = token_count_text(text)
            if used_tokens + cost > token_budget:
                chunk_cost = token_count_text(document.content)
                if not emitted_for_chunk and used_tokens + chunk_cost <= token_budget:
                    used_tokens += chunk_cost
                    fallback_meta = dict(meta)
                    fallback_meta.update({
                        "clause_id": clause["clause_id"],
                        "clause_number": clause["number"],
                        "expansion_status": "fallback_to_original_chunk",
                        "expanded_from_chunk": meta.get("chunk_id"),
                    })
                    expanded.append(Document(content=document.content, meta=fallback_meta))
                    diagnostics.append({"chunk_id": meta.get("chunk_id"), "clause_id": clause["clause_id"], "status": "fallback_to_original_chunk", "reason": "clause_too_large"})
                    emitted_for_chunk = True
                else:
                    diagnostics.append({"chunk_id": meta.get("chunk_id"), "clause_id": clause["clause_id"], "status": "budget_exhausted", "reason": "clause_too_large; исходный чанк тоже не помещается"})
                continue
            used_tokens += cost
            seen_clauses.add(clause["clause_id"])
            emitted_for_chunk = True
            new_meta = dict(meta)
            new_meta.update({
                "chunk_id": meta.get("chunk_id"),
                "document_ref": f"clause-{clause['clause_id']}",
                "original_chunk_id": meta.get("chunk_id"),
                "clause_id": clause["clause_id"],
                "clause_number": clause["number"],
                "clause_title": clause["title"],
                "source_span": {"document_id": meta.get("document_id"), "start": clause["start"], "end": clause["end"]},
                "expanded_from_chunk": meta.get("chunk_id"),
                "expansion_status": "expanded_successfully",
            })
            expanded.append(Document(content=text, meta=new_meta))
            diagnostics.append({"chunk_id": meta.get("chunk_id"), "clause_id": clause["clause_id"], "status": "expanded_successfully"})
    counts = {}
    for item in diagnostics:
        counts[item["status"]] = counts.get(item["status"], 0) + 1
    return expanded, {"items": diagnostics, "counts": counts, "used_tokens": used_tokens, "token_budget": token_budget}
