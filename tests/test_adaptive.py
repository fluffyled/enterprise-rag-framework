from types import SimpleNamespace

import pytest

from navigator.adaptive_retrieval import adaptive_analysis, local_query_plan, query_expansion
from navigator.config import load_config


def document(identifier, document_id, score):
    return SimpleNamespace(id=identifier, content=f"текст {identifier}", meta={"rerank_score": score, "document_id": document_id})


def test_adaptive_trigger_and_limit():
    config = load_config({"retrieval": {"adaptive_min_candidates": 3, "adaptive_min_unique_documents": 2, "adaptive_min_score": -2}})
    analysis = adaptive_analysis("question", [document("a", "one", -3)], config)
    assert not analysis["sufficient"]
    assert "few_candidates" in analysis["reasons"] and "low_relative_relevance" in analysis["reasons"]
    assert len(query_expansion("Какой срок подачи заявки и кто должен утвердить документ?")) <= 2


def test_adaptive_sufficient_result():
    config = load_config()
    documents = [document(str(index), f"doc-{index}", 1) for index in range(5)]
    assert adaptive_analysis("question", documents, config)["sufficient"]


def test_external_query_planner_is_blocked():
    with pytest.raises(ValueError):
        local_query_plan("question", "https://external.example/v1/chat/completions")
