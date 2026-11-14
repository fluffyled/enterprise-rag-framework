"""Convert retrieval results into source-addressed generation inputs."""
import hashlib
import json
from types import SimpleNamespace

from answering.v2.contracts import Evidence


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def adapt_evidence(documents, mode, source_documents=(), clause_store=None, *, add_parents=False):
    corpus = {row["document_id"]: row for row in source_documents}
    evidence = {}
    inputs = list(documents)
    parent_limit = len(inputs) + 2
    queued = {(item.meta.get("document_id"), item.meta.get("clause_id")) for item in inputs}
    for document in inputs:
        meta = document.meta
        document_id = meta.get("document_id") or meta.get("relative_path") or meta.get("name")
        if not document_id:
            raise ValueError("У фрагмента отсутствует идентификатор документа")
        content = document.content
        if not content or not content.strip():
            continue
        span = meta.get("source_span") or {}
        start, end = span.get("start"), span.get("end")
        source = corpus.get(document_id, {})
        version = meta.get("sha256") or meta.get("document_version_id")
        coordinates = []
        if source.get("sha256") == version and source.get("text") and (
            type(start) is int and type(end) is int and 0 <= start < end <= len(source["text"])
        ):
            original = source["text"][start:end].strip()
            if " ".join(original.split()) == " ".join(content.split()):
                leading = len(source["text"][start:end]) - len(source["text"][start:end].lstrip())
                content = original
                coordinates = [(start + leading, start + leading + len(content))]
        expanded = meta.get("expansion_status") == "expanded_successfully"
        node_id = meta.get("clause_id") if expanded else None
        entry = (clause_store or {}).get(version, {})
        clause = next((row for row in entry.get("clauses", [])
                       if row["clause_id"] == node_id), {}) if entry.get("document_id") == document_id else {}
        key = node_id or meta.get("chunk_id") or document.id
        fingerprint = digest(content)
        evidence_id = "E" + digest(json.dumps([document_id, version, key, fingerprint]))[:24]
        locator = meta.get("locator")
        page = meta.get("page")
        if expanded:
            locator = f"п. {meta['clause_number']}" if meta.get("clause_number") else None
            unit = meta.get("unit_source_span") or {}
            if not coordinates or unit.get("start", end) > start or unit.get("end", start) < coordinates[0][1]:
                page = None
            if page:
                locator = f"{locator}, стр. {page}" if locator else f"стр. {page}"
        parent_id = None if clause.get("parent_ambiguous") else clause.get("parent_id")
        parent_key = document_id, parent_id
        if add_parents and parent_id and coordinates and len(inputs) < parent_limit and parent_key not in queued:
            parent = next((row for row in entry["clauses"] if row["clause_id"] == parent_id), None)
            if parent and parent["start"] <= start < end <= parent["end"] and len(parent["full_text"]) <= 1500:
                queued.add(parent_key)
                inputs.append(SimpleNamespace(content=parent["full_text"], meta={
                    **meta, "clause_id": parent_id, "clause_number": parent["number"],
                    "source_span": {"start": parent["start"], "end": parent["end"]},
                }))
        evidence[evidence_id] = Evidence(
            id=evidence_id, document_id=document_id, document_title=meta.get("name") or document_id,
            full_text=content, locator=locator, node_id=node_id,
            parent_id=parent_id if expanded else meta.get("parent_id"),
            section_path=[meta["section"]] if meta.get("section") else [],
            source_spans=coordinates, source_hash=fingerprint, document_version=version,
            metadata={
                "chunk_id": meta.get("chunk_id"), "retrieval_mode": mode,
                "expansion_status": meta.get("expansion_status"),
                "clause_number": meta.get("clause_number"),
                "retrieved_locator": meta.get("locator"), "retrieved_page": meta.get("page"),
                "page": page, "relative_path": meta.get("relative_path"),
                "incomplete": not expanded and (meta.get("word_start", 0) > 0
                    or (meta.get("unit_source_span") or {}).get("end", 0) > (end or 0)
                    or meta.get("expansion_status") == "fallback_to_original_chunk"),
            },
        )
    return list(evidence.values())


def validate_citation(evidence, quote):
    if not isinstance(quote, str) or not quote.strip() or quote not in evidence.full_text:
        raise ValueError("Цитата не совпадает с исходным фрагментом")
