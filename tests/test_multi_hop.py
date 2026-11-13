from types import SimpleNamespace

from haystack import Document

from navigator.multi_hop import multi_hop_search


def make_document(chunk_id, score, content="текст доказательства"):
    return Document(content=content, meta={"chunk_id": chunk_id, "rerank_score": score})


def make_retriever(per_query_docs):
    def hybrid(question, config):
        return [], [], per_query_docs.get(question, []), {}

    def rerank(question, documents):
        return sorted(documents, key=lambda document: document.meta.get("rerank_score", 0.0), reverse=True)

    return SimpleNamespace(_hybrid_search=hybrid, _rerank=rerank)


def make_settings(**overrides):
    settings = {"candidate_top_k": 20, "output_top_k": 6, "context_token_budget": 4000, "parent_expansion": False, "related_clauses": False}
    settings.update(overrides)
    return {"retrieval": settings}


def test_multi_hop_merges_candidates_and_tracks_origin():
    docs_a = [make_document("a1", 5.0), make_document("shared", 1.0)]
    docs_b = [make_document("b1", 4.0), make_document("shared", 3.0)]
    retriever = make_retriever({"вопрос": docs_a, "подзадача": docs_b})
    settings = make_settings()
    metadata, timings = {}, {}
    import navigator.multi_hop as mh
    original = mh.plan_subtasks
    mh.plan_subtasks = lambda question, use_llm=True: (["вопрос", "подзадача"], "test")
    try:
        selected = multi_hop_search(retriever, "вопрос", settings, metadata, timings)
    finally:
        mh.plan_subtasks = original
    assert [document.meta["chunk_id"] for document in selected] == ["a1", "b1", "shared"]
    assert metadata["multi_hop"]["subtasks"][1]["supported"] is True


def test_multi_hop_marks_unsupported_requirements():
    retriever = make_retriever({"вопрос": [make_document("a1", -5.0)]})
    settings = make_settings()
    metadata, timings = {}, {}
    import navigator.multi_hop as mh
    original = mh.plan_subtasks
    mh.plan_subtasks = lambda question, use_llm=True: (["вопрос", "незнакомый запрос"], "test")
    try:
        multi_hop_search(retriever, "вопрос", settings, metadata, timings)
    finally:
        mh.plan_subtasks = original
    coverage = metadata["multi_hop"]["subtasks"]
    assert coverage[1]["supported"] is False
    assert "незнакомый запрос" in metadata["multi_hop"]["unsupported_after_rounds"]


def test_multi_hop_round_limit():
    calls = []

    def hybrid(question, config):
        calls.append(question)
        return [], [], [make_document(f"doc-{question}", 1.0)], {}

    retriever = SimpleNamespace(_hybrid_search=hybrid, _rerank=lambda question, documents: documents)
    settings = make_settings(multi_hop_rounds=2)
    metadata, timings = {}, {}
    import navigator.multi_hop as mh
    original = mh.plan_subtasks
    mh.plan_subtasks = lambda question, use_llm=True: (["вопрос", "подзадача"], "test")
    try:
        multi_hop_search(retriever, "вопрос", settings, metadata, timings)
    finally:
        mh.plan_subtasks = original
    # раунд 0: вопрос + подзадача; подзадача поддержана (score 1.0) — второго раунда нет
    assert calls == ["вопрос", "подзадача"]
    assert len(metadata["multi_hop"]["rounds"]) == 1
