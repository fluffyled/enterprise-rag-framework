import json

from haystack import Document

from navigator.parent_expansion import expand_parents, load_clause_store


def make_store():
    return {
        "sha1": {
            "document_id": "doc.pdf",
            "clauses": [
                {"clause_id": "c1", "document_id": "doc.pdf", "number": "3", "level": 1, "title": "3. Раздел", "full_text": "3. Раздел Полный текст раздела со списком.", "start": 0, "end": 100, "parent_id": None},
                {"clause_id": "c2", "document_id": "doc.pdf", "number": "3.1", "level": 2, "title": "3.1. Пункт", "full_text": "3.1. Пункт Полный текст пункта.", "start": 20, "end": 60, "parent_id": "c1"},
                {"clause_id": "c3", "document_id": "doc.pdf", "number": "3.2", "level": 2, "title": "3.2. Другой", "full_text": "3.2. Другой Полный текст другого пункта.", "start": 60, "end": 100, "parent_id": "c1"},
            ],
        }
    }


def make_chunk(start, sha="sha1"):
    return Document(content="кусок текста", meta={
        "sha256": sha, "chunk_id": f"chunk-{start}", "document_id": "doc.pdf",
        "source_span": {"document_id": "doc.pdf", "start": start, "end": start + 20},
    })


def test_expand_replaces_chunk_with_full_clause():
    store = make_store()
    result = expand_parents([make_chunk(25)], store, token_budget=1000)
    assert [document.meta["clause_id"] for document in result] == ["c1", "c2"]
    assert result[1].content == "3.1. Пункт Полный текст пункта."
    assert result[1].meta["clause_number"] == "3.1"
    assert result[1].meta["expanded_from_chunk"] == "chunk-25"


def test_expand_dedupes_same_clause():
    store = make_store()
    result = expand_parents([make_chunk(25), make_chunk(30), make_chunk(70)], store, token_budget=1000)
    assert [document.meta["clause_id"] for document in result] == ["c1", "c2", "c3"]


def test_expand_respects_token_budget():
    store = make_store()
    result = expand_parents([make_chunk(25), make_chunk(70)], store, token_budget=5)
    assert result == []


def test_expand_keeps_chunk_without_clause_match():
    store = make_store()
    orphan = Document(content="сирота", meta={"sha256": "unknown", "chunk_id": "x", "document_id": "other.pdf", "source_span": {"document_id": "other.pdf", "start": 0, "end": 5}})
    result = expand_parents([orphan], store, token_budget=1000)
    assert len(result) == 1
    assert result[0].content == "сирота"


def test_store_loads():
    store = load_clause_store()
    assert isinstance(store, dict)
    assert all("clauses" in entry for entry in store.values())


def test_related_clauses_add_referenced_clause():
    store = make_store()
    store["sha1"]["clauses"][1]["references"] = ["c3"]
    result = expand_parents([make_chunk(25)], store, token_budget=1000, related_clauses=True)
    assert [document.meta["clause_id"] for document in result] == ["c1", "c2", "c3"]


def test_related_clauses_off_by_default():
    store = make_store()
    store["sha1"]["clauses"][1]["references"] = ["c3"]
    result = expand_parents([make_chunk(25)], store, token_budget=1000)
    assert [document.meta["clause_id"] for document in result] == ["c1", "c2"]
