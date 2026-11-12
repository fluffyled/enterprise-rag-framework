from navigator.config import load_config
from navigator.contextual import build_contextual_representation, prepare_contextual_chunks
from navigator.structure import enrich_hierarchy


def sample_chunk():
    return {"id": "chunk", "content": "Исходная норма.", "meta": {"chunk_id": "chunk", "document_id": "doc", "relative_path": "doc", "document_version_id": "v1", "name": "Регламент", "section": "2. Порядок", "source_span": {"document_id": "doc", "start": 0, "end": 15}}}


def test_contextual_representation_preserves_original():
    chunk = sample_chunk()
    nodes = enrich_hierarchy([chunk])
    config = load_config({"retrieval": {"contextual": True, "contextual_mode": "parent"}})
    prepare_contextual_chunks([chunk], nodes, config)
    assert chunk["meta"]["original_content"] == "Исходная норма."
    assert chunk["meta"]["search_content"] == chunk["content"]
    assert "Регламент" in chunk["content"] and "2. Порядок" in chunk["content"]
    assert chunk["content"].endswith("Исходная норма.")
    assert chunk["meta"]["source_span"] == {"document_id": "doc", "start": 0, "end": 15}


def test_header_mode_does_not_add_parent_text():
    chunk = sample_chunk()
    representation = build_contextual_representation(chunk, {"contextual_mode": "headers", "sections": {}, "chunks": {}})
    assert representation == "Регламент\n2. Порядок\nИсходная норма."


def test_rerank_restores_original_without_mutating_store_document():
    from haystack import Document
    from navigator.retrieval import Retriever
    document = Document(content="search representation", meta={"original_content": "original quote"})
    retriever = Retriever.__new__(Retriever)
    retriever.ranker = None
    restored = retriever._rerank("q", [document])
    assert document.content == "search representation"
    assert restored[0].content == "original quote"
