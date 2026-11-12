import json

from haystack import Document

from navigator.evaluation.benchmark import run_benchmark, save_benchmark
from navigator.retrieval import SearchResults, document_snapshot


class FakeRetriever:
    def search(self, question, top_k=6, config=None):
        document = Document(content="gold evidence", meta={"document_id": "doc", "chunk_id": "chunk", "source_span": {"document_id": "doc", "start": 0, "end": 13}})
        timings = {key: 0.001 for key in ("embedding", "bm25", "dense", "rrf", "reranking", "context_selection", "total")}
        stages = {"cross_encoder": [document_snapshot(document, 1)], "selected_context": [document_snapshot(document, 1)]}
        return SearchResults([document], stages, timings)


def test_benchmark_saves_complete_artifacts(tmp_path):
    dataset = {"name": "synthetic", "queries": [{"id": "q", "question": "q", "answerable": True, "question_type": "simple", "gold_document_ids": ["doc"], "evidence_groups": [{"alternatives": [{"document_id": "doc", "start": 0, "end": 13}]}]}]}
    result = run_benchmark(FakeRetriever(), dataset)
    save_benchmark(result, tmp_path, {"seed": 42})
    assert result["metrics"]["evidence_recall@6"] == 1
    for name in ("config.json", "metrics.json", "per_query_results.json", "latency.json", "comparison.md", "errors.md"):
        assert (tmp_path / name).exists()
    assert json.loads((tmp_path / "per_query_results.json").read_text(encoding="utf-8"))[0]["gold_document_ids"] == ["doc"]
