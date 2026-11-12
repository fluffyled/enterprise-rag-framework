import pytest

from navigator.evaluation.metrics import context_metrics, document_metrics, evidence_metrics, paired_bootstrap, per_query_metrics


def result(document_id, start, end, content="содержательный текст фрагмента"):
    return {"id": f"{document_id}-{start}", "document_id": document_id, "content": content, "source_span": {"document_id": document_id, "start": start, "end": end}}


def test_documents_are_deduplicated_before_document_metrics():
    results = [result("a", 0, 10), result("a", 20, 30), result("b", 0, 10)]
    metrics = document_metrics(results, ["b"])
    assert metrics["document_hit@1"] == 0
    assert metrics["document_hit@3"] == 1
    assert metrics["mrr@5"] == 0.5
    assert metrics["ranked_document_count"] == 2


def test_and_groups_require_all_and_or_alternatives_are_equivalent():
    case = {"evidence_groups": [
        {"id": "first", "alternatives": [{"document_id": "a", "start": 0, "end": 10}, {"document_id": "b", "start": 0, "end": 10}]},
        {"id": "second", "alternatives": [{"document_id": "c", "start": 20, "end": 40}]},
    ]}
    metrics = evidence_metrics([result("b", 0, 10), result("c", 20, 40)], case)
    assert metrics["evidence_recall@6"] == 1
    assert metrics["all_evidence_hit@6"] == 1
    partial = evidence_metrics([result("a", 0, 5)], case)
    assert partial["evidence_recall@6"] == 0.5
    assert partial["all_evidence_hit@6"] == 0
    assert partial["gold_span_coverage@6"] == 0.25


def test_span_alignment_does_not_require_chunk_ids():
    case = {"gold_document_ids": ["a"], "evidence_groups": [{"alternatives": [{"document_id": "a", "start": 100, "end": 200}]}]}
    metrics = per_query_metrics([result("a", 120, 180)], case)
    assert metrics["evidence_recall@6"] == 1
    assert metrics["gold_span_coverage"] == pytest.approx(0.6)


def test_context_precision_and_redundancy():
    case = {"evidence_groups": [{"alternatives": [{"document_id": "a", "start": 0, "end": 5}]}]}
    repeated = "один два три четыре пять"
    metrics = context_metrics([result("a", 0, 10, repeated), result("b", 0, 10, repeated)], case)
    assert metrics["evidence_precision"] == 0.25
    assert metrics["redundancy_ratio"] == 0.5
    assert metrics["unique_documents"] == 2


def test_graded_ndcg_and_pair_bootstrap():
    high = document_metrics([result("a", 0, 1), result("b", 0, 1)], ["a", "b"], {"a": 3, "b": 1})
    low = document_metrics([result("b", 0, 1), result("a", 0, 1)], ["a", "b"], {"a": 3, "b": 1})
    assert high["ndcg@5"] > low["ndcg@5"]
    assert high["document_mrr@10"] == 1
    assert high["document_ndcg@10"] > low["document_ndcg@10"]
    assert high["document_recall@10"] == 1
    interval = paired_bootstrap([{"x": 0}, {"x": 1}], [{"x": 1}, {"x": 1}], "x", iterations=100)
    assert interval["difference"] == 0.5 and interval["n"] == 2
