import json
from types import SimpleNamespace

from navigator.enrichment_search import _fact_text
from navigator.multi_hop import multi_hop_search


def test_fact_text_joins_fields():
    card = {"action": "Подать записку", "object": "руководителю", "deadline": "5 дней", "condition": ""}
    assert _fact_text(card) == "Подать записку руководителю 5 дней"


def test_enrichment_channel_injects_clause_candidates():
    docs_main = [SimpleNamespace(id="d1", meta={"chunk_id": "d1", "rerank_score": 5.0}, content="текст")]

    def hybrid(question, config):
        return [], [], docs_main, {}

    retriever = SimpleNamespace(_hybrid_search=hybrid, _rerank=lambda q, ds: ds, model=None)

    class FakeIndex:
        def search(self, question, top_k=10, include_facts=True):
            return ["clauseX"]

    from haystack import Document

    def fake_clause_documents(retriever, clause_ids, store=None):
        return [Document(content="полный пункт X", meta={"chunk_id": "enrich-clauseX", "rerank_score": 0.0})]

    import navigator.enrichment_search as es
    import navigator.multi_hop as mh
    original_index, original_docs = es.EnrichmentIndex, es.clause_documents
    es.EnrichmentIndex = lambda model=None: FakeIndex()
    es.clause_documents = fake_clause_documents
    original_plan = mh.plan_subtasks
    mh.plan_subtasks = lambda question, use_llm=True: (["вопрос"], "test")
    try:
        settings = {"retrieval": {"candidate_top_k": 20, "output_top_k": 6, "context_token_budget": 4000, "parent_expansion": False, "related_clauses": False, "multi_hop_rounds": 1, "enrichment_search": True, "enrichment_facts": False}}
        metadata, timings = {}, {}
        selected = multi_hop_search(retriever, "вопрос", settings, metadata, timings)
        keys = [document.meta["chunk_id"] for document in selected]
        assert "enrich-clauseX" in keys
        assert metadata["multi_hop"]["enrichment_clauses"] == 1
    finally:
        es.EnrichmentIndex, es.clause_documents = original_index, original_docs
        mh.plan_subtasks = original_plan


def test_enrichment_off_by_default():
    docs_main = [SimpleNamespace(id="d1", meta={"chunk_id": "d1", "rerank_score": 5.0}, content="текст")]

    def hybrid(question, config):
        return [], [], docs_main, {}

    retriever = SimpleNamespace(_hybrid_search=hybrid, _rerank=lambda q, ds: ds, model=None)
    import navigator.multi_hop as mh
    original_plan = mh.plan_subtasks
    mh.plan_subtasks = lambda question, use_llm=True: (["вопрос"], "test")
    try:
        settings = {"retrieval": {"candidate_top_k": 20, "output_top_k": 6, "context_token_budget": 4000, "parent_expansion": False, "related_clauses": False, "multi_hop_rounds": 1}}
        metadata, timings = {}, {}
        selected = multi_hop_search(retriever, "вопрос", settings, metadata, timings)
        assert not hasattr(retriever, "_enrichment_index")
        assert "enrichment_clauses" not in metadata["multi_hop"]
    finally:
        mh.plan_subtasks = original_plan
