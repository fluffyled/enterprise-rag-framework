import json

import pytest
from haystack import Document

from navigator.parent_expansion import expand_parents, load_clause_store


def make_store(clauses_by_sha):
    return {
        sha: {"document_id": clauses[0]["document_id"], "clauses": clauses}
        for sha, clauses in clauses_by_sha.items()
    }


def make_clause(cid, number, text, start, end, sha="sha1"):
    return {"clause_id": cid, "document_id": "doc.pdf", "number": number, "level": number.count(".") + 1, "title": text[:40], "full_text": text, "start": start, "end": end, "parent_id": None, "references": []}


def make_chunk(start, sha="sha1", content="кусок текста", chunk_id="chunk-1", document_id="doc.pdf"):
    return Document(content=content, meta={
        "sha256": sha, "chunk_id": chunk_id, "document_id": document_id,
        "page": "2", "locator": "абзац 5",
        "source_span": {"document_id": document_id, "start": start, "end": start + len(content)},
    })


def test_expand_contract_fields():
    store = make_store({"sha1": [make_clause("c2", "3.1", "3.1. Пункт Полный текст пункта.", 20, 60)]})
    docs, diag = expand_parents([make_chunk(25)], store, token_budget=1000)
    assert len(docs) == 1
    meta = docs[0].meta
    assert meta["chunk_id"] == "chunk-1"  # исходный чанк сохранён
    assert meta["clause_id"] == "c2" and meta["clause_number"] == "3.1"
    assert meta["page"] == "2" and meta["locator"] == "абзац 5"
    assert meta["source_span"]["start"] == 20 and meta["source_span"]["end"] == 60
    assert meta["expansion_status"] == "expanded_successfully"
    assert meta["expanded_from_chunk"] == "chunk-1"
    assert diag["counts"] == {"expanded_successfully": 1}


def test_fallback_when_clause_too_large_but_chunk_fits():
    big_clause = make_clause("c1", "3", "слово " * 500, 0, 3500)
    store = make_store({"sha1": [big_clause]})
    chunk = make_chunk(10, content="маленький чанк")
    docs, diag = expand_parents([chunk], store, token_budget=50)
    assert len(docs) == 1
    assert docs[0].content == "маленький чанк"
    assert docs[0].meta["expansion_status"] == "fallback_to_original_chunk"
    assert diag["counts"]["fallback_to_original_chunk"] == 1


def test_budget_exhausted_reported_not_silent():
    big_clause = make_clause("c1", "3", "слово " * 500, 0, 3500)
    store = make_store({"sha1": [big_clause]})
    big_chunk = make_chunk(10, content="слово " * 300)
    docs, diag = expand_parents([big_chunk], store, token_budget=10)
    assert docs == []
    assert diag["counts"]["budget_exhausted"] == 1
    assert "не помещается" in diag["items"][0]["reason"]


def test_missing_clause_falls_back_to_chunk():
    store = make_store({"sha1": [make_clause("c1", "9", "9. Другой пункт далеко.", 500, 560)]})
    docs, diag = expand_parents([make_chunk(10)], store, token_budget=1000)
    assert len(docs) == 1 and docs[0].content == "кусок текста"
    assert diag["items"][0]["status"] == "fallback_to_original_chunk"
    assert diag["items"][0]["reason"] == "missing_clause"


def test_invalid_source_span_falls_back():
    store = make_store({"sha1": [make_clause("c1", "3", "3. Пункт.", 0, 20)]})
    bad = Document(content="текст", meta={"sha256": "sha1", "chunk_id": "x", "document_id": "doc.pdf", "source_span": {"start": None, "end": 5}})
    docs, diag = expand_parents([bad], store, token_budget=1000)
    assert diag["items"][0]["reason"] == "invalid_source_span"


def test_identical_texts_from_different_docs_not_merged():
    clause_a = make_clause("cA", "1", "1. Одинаковый текст пункта.", 0, 40, sha="shaA")
    clause_b = make_clause("cB", "1", "1. Одинаковый текст пункта.", 0, 40, sha="shaB")
    clause_b["document_id"] = "other.pdf"
    store = make_store({"shaA": [clause_a], "shaB": [clause_b]})
    docs, diag = expand_parents([make_chunk(5, sha="shaA"),
                                 make_chunk(5, sha="shaB", chunk_id="chunk-2", document_id="other.pdf")],
                                store, token_budget=1000)
    assert len(docs) == 2
    assert {d.meta["clause_id"] for d in docs} == {"cA", "cB"}


def test_shared_sha_does_not_borrow_clause_from_another_document():
    store = make_store({"sha1": [make_clause("c1", "3", "3. Пункт.", 0, 20)]})
    chunk = make_chunk(5, document_id="copy.pdf")
    docs, diag = expand_parents([chunk], store, token_budget=1000)
    assert docs == [chunk]
    assert diag["items"][0]["reason"] == "missing_clause"


def test_identical_docx_versions_keep_distinct_chunks_and_clauses(tmp_path):
    from docx import Document as WordDocument
    from navigator.ingest import ingest, units
    from scripts.build_clause_store import build_store

    raw = tmp_path / "raw"
    raw.mkdir()
    original = WordDocument()
    original.add_paragraph("1. Сотрудник передаёт заявление ответственному лицу.")
    table = original.add_table(rows=1, cols=3)
    for cell, value in zip(table.rows[0].cells, ("Да", "Да", "Нет"), strict=True):
        cell.text = value
    original.save(raw / "first.docx")
    (raw / "second.docx").write_bytes((raw / "first.docx").read_bytes())
    assert list(units(raw / "first.docx"))[1][0] == "Да | Да | Нет"
    chunks = ingest(raw, tmp_path)
    assert len({chunk["id"] for chunk in chunks}) == len(chunks)
    docs = json.loads((tmp_path / "source_documents.json").read_text(encoding="utf-8"))
    payload = build_store(docs)
    path = tmp_path / "clauses.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    store = load_clause_store(path)
    assert len(store) == 2
    ids = {entry["clauses"][0]["clause_id"] for entry in store.values()}
    assert len(ids) == 2
    (raw / "first.docx").unlink()
    ingest(raw, tmp_path)
    remaining = build_store(json.loads((tmp_path / "source_documents.json").read_text(encoding="utf-8")))
    assert remaining["documents"] == [payload["documents"][1]]


def test_failed_rebuild_preserves_diagnostic_and_previous_snapshot(tmp_path):
    from navigator.corpus import rebuild

    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "broken.docx").write_bytes(b"not a zip")
    snapshots = tmp_path / "snapshots"
    previous = snapshots / "previous"
    previous.mkdir(parents=True)
    with pytest.raises(RuntimeError, match="broken.docx"):
        rebuild(snapshots, raw=raw)
    assert {item.name for item in snapshots.iterdir()} == {"previous", "last_build_error.json"}
    assert "broken.docx" in (snapshots / "last_build_error.json").read_text(encoding="utf8")


def test_budget_never_exceeded():
    store = make_store({"sha1": [make_clause(str(i), f"1.{i}", f"1.{i}. Пункт {'слово ' * 50}", i * 400, i * 400 + 300) for i in range(1, 6)]})
    chunks = [make_chunk(i * 400 + 10, chunk_id=f"c{i}") for i in range(1, 6)]
    docs, diag = expand_parents(chunks, store, token_budget=200)
    total = sum(len(d.content.split()) for d in docs)
    assert total <= 200 + 6  # запас на знаки препинания словесного счётчика


def test_store_loads():
    store = load_clause_store()
    assert isinstance(store, dict)
    assert all("clauses" in entry for entry in store.values())
