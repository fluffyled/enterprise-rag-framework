from types import SimpleNamespace

from navigator.coverage import rank_normalize
from navigator.query_analysis import decompose_question, retrieval_queries
from navigator.selection import select_coverage, select_deduplicated, select_mmr


def document(identifier, text, score):
    return SimpleNamespace(id=identifier, content=text, score=score, meta={"rerank_score": score})


def test_query_decomposition_preserves_source_intervals():
    question = "Какой срок подачи заявки и кто должен утвердить документ?"
    tasks = decompose_question(question)
    assert len(tasks) == 2
    for task in tasks:
        assert question[task.source_span["start"]:task.source_span["end"]] == task.text
    queries, _ = retrieval_queries(question, decompose=True)
    assert queries[0] == question


def test_short_question_is_not_decomposed():
    tasks = decompose_question("Кто утверждает приказ?")
    assert len(tasks) == 1 and tasks[0].text == "Кто утверждает приказ?"


def test_rank_normalization_is_not_raw_probability():
    assert rank_normalize([-2, 4, 0]) == [0.0, 1.0, 0.5]


def test_deduplication_and_mmr_limit_redundancy():
    documents = [document("a", "срок подачи заявки пять дней", 4), document("b", "срок подачи заявки пять дней", 3), document("c", "документ утверждает проректор", 2)]
    selected = select_deduplicated(documents, 3, 200)
    assert [item.id for item in selected] == ["a", "c"]
    assert select_mmr(documents, 2, 200, mmr_lambda=0.5)[1].id == "c"


def test_coverage_greedy_selects_complementary_evidence_within_budget():
    documents = [document("a", "срок пять дней и проректор", 4), document("b", "срок пять дней и проректор", 3), document("c", "иные сведения", 1)]
    queries = ["срок", "кто утверждает"]
    matrix = {"срок": [1.0, 0.8, 0.0], "кто утверждает": [0.2, 0.1, 0.0]}
    selected = select_coverage(documents, 2, 200, queries, matrix)
    assert [item.id for item in selected] == ["a", "b"]
    limited = select_coverage(documents, 3, 8, queries, matrix)
    assert sum(len(item.content.split()) for item in limited) <= 8


def test_stable_and_baseline_configs_are_distinct():
    from navigator.config import load_config
    from navigator.settings import ROOT
    baseline = load_config(ROOT / "configs" / "retrieval_baseline.yaml")
    stable = load_config(ROOT / "configs" / "retrieval_stable.yaml")
    fast = load_config(ROOT / "configs" / "retrieval_fast_stable.yaml")
    quality = load_config(ROOT / "configs" / "retrieval_quality_stable.yaml")
    assert not baseline["retrieval"]["coverage_aware"]
    # v4.1 stable = Fast (BGE-M3 + bge-reranker + adaptive); выбор Quality —
    # явный, через NAVIGATOR_CONFIG=configs/retrieval_quality_stable.yaml
    assert stable["retrieval"]["embedding_backend"] == "bge-m3-sparse"
    assert stable["retrieval"]["reranker_backend"] == "bge-reranker-v2-m3"
    assert fast["retrieval"]["selection_strategy"] == stable["retrieval"]["selection_strategy"]
    assert quality["retrieval"]["parent_expansion"] is True
    assert not stable["retrieval"]["multi_hop"] and not stable["retrieval"]["parent_expansion"]


def test_improved_decomposition_preserves_spans_context_and_dependencies():
    from navigator.query_analysis import decompose_question_improved
    question = "Какой срок подачи заявки и кто утверждает документ при наличии условия?"
    tasks = decompose_question_improved(question)
    assert len(tasks) >= 2
    for task in tasks:
        assert question[task.source_span["start"]:task.source_span["end"]] == task.text
        assert task.context == question
    assert tasks[-1].depends_on


def test_planner_falls_back_to_improved_rules(monkeypatch):
    import urllib.request
    from navigator.query_analysis import local_llm_decompose
    monkeypatch.setattr(urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")))
    question = "Какой срок подачи заявки и кто утверждает документ?"
    tasks = local_llm_decompose(question)
    assert len(tasks) >= 2
    assert all(question[task.source_span["start"]:task.source_span["end"]] == task.text for task in tasks)


def test_coverage_optional_strategies_preserve_budget_and_source_metadata():
    first = document("a", "срок пять дней", 4)
    first.meta["document_id"] = "doc-a"
    second = document("b", "срок четыре дня", 3)
    second.meta["document_id"] = "doc-a"
    third = document("c", "документ утверждает проректор", 2)
    third.meta["document_id"] = "doc-c"
    documents = [first, second, third]
    queries = ["срок", "кто утверждает"]
    matrix = {"срок": [1.0, 0.9, 0.0], "кто утверждает": [0.0, 0.0, 1.0]}
    selected = select_coverage(documents, 2, 200, queries, matrix, coverage_min_subtask=True, coverage_document_diversity=0.05)
    assert [item.id for item in selected] == ["a", "c"]
    assert selected[1].meta["document_id"] == "doc-c"
    without_cost = select_coverage(documents, 2, 200, queries, matrix, coverage_cost_normalization=False, coverage_lambda=0.0)
    assert len(without_cost) == 2
