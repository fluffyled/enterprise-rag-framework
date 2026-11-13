from navigator.evaluation.alignment import normalize_evidence_groups
from navigator.evaluation.error_analysis import classify_group, direct_gold_oracle, oracle_results


def result(span=(0, 10)):
    return {"id": "chunk", "chunk_id": "chunk", "document_id": "doc", "content": "gold", "source_span": {"document_id": "doc", "start": span[0], "end": span[1]}}


def row(stages):
    return {"metrics": {"selected_tokens": 10}, "trace": {"metadata": {"subtasks": []}, "stages": stages}}


def case():
    return {"id": "q", "question": "gold", "answerable": True, "evidence_groups": [{"id": "g", "alternatives": [{"document_id": "doc", "start": 0, "end": 4, "text": "gold"}]}]}


def chunks():
    return [{"id": "chunk", "meta": {"document_id": "doc", "source_span": {"document_id": "doc", "start": 0, "end": 10}}}]


def test_error_classification_and_oracle_stages():
    group = normalize_evidence_groups(case())[0]
    stages = {stage: [] for stage in ("bm25", "dense", "rrf", "cross_encoder", "selected_context")}
    assert classify_group(row(stages), group, chunks(), sources={"doc": "gold"})["category"] == "Candidate Retrieval Error"
    stages["bm25"] = [result()]
    stages["selected_context"] = [result()]
    assert classify_group(row(stages), group, chunks(), sources={"doc": "gold"})["category"] is None
    stages["selected_context"] = []
    assert classify_group(row(stages), group, chunks(), sources={"doc": "gold"})["category"] == "Fusion Error"
    stages["rrf"] = [result()]
    stages["cross_encoder"] = [result()]
    assert classify_group(row(stages), group, chunks(), sources={"doc": "gold"})["category"] == "Selection Error"
    oracle = oracle_results(row(stages), case())
    assert oracle["oracle_c_reranked"]["evidence_recall"] == 1
    assert direct_gold_oracle(case())["oracle_d_direct_gold"]["evidence_recall"] == 1


def test_parsing_error_has_precedence():
    group = normalize_evidence_groups(case())[0]
    stages = {stage: [] for stage in ("bm25", "dense", "rrf", "cross_encoder", "selected_context")}
    error = classify_group(row(stages), group, chunks(), sources={"doc": "different"})
    assert error["category"] == "Parsing Error"
