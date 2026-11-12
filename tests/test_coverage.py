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
    assert not baseline["retrieval"]["coverage_aware"]
    assert stable["retrieval"]["coverage_aware"]
    assert stable["retrieval"]["selection_strategy"] == "coverage_decomposed"
    assert stable["retrieval"]["embedding_backend"] == "e5-small"
    assert not stable["retrieval"]["hierarchical"] and not stable["retrieval"]["adaptive"]
