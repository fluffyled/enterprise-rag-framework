import pytest
from haystack import Document

from navigator.selection import select_context, select_protected_coverage


def make_documents(scores, texts=None):
    texts = texts or [f"документ номер {index} с уникальным содержимым {index}" for index in range(len(scores))]
    return [Document(content=text, meta={"rerank_score": score}) for text, score in zip(texts, scores)]


def make_matrix(documents, query_scores):
    return {"q0": query_scores, "q1": [score * 0.5 for score in query_scores]}


def test_protected_coverage_keeps_top_p_unconditionally():
    documents = make_documents([10.0, 9.0, 1.0, 0.5, 0.2, 0.1])
    matrix = make_matrix(documents, [1.0, 0.9, 0.0, 0.0, 0.0, 0.0])
    selected = select_protected_coverage(documents, top_k=3, token_budget=10000, queries=["q0", "q1"], matrix=matrix, protected_top_p=2)
    assert selected[:2] == documents[:2]


def test_protected_coverage_fills_remaining_slots_by_score():
    documents = make_documents([5.0, 4.0, 3.0, 2.0, 1.0, 0.5])
    matrix = make_matrix(documents, [0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    selected = select_protected_coverage(documents, top_k=4, token_budget=10000, queries=["q0", "q1"], matrix=matrix, protected_top_p=1, coverage_alpha=1.0, coverage_beta=0.0, coverage_gamma=0.0)
    assert selected[0] == documents[0]
    assert selected[1:] == documents[1:4]


def test_protected_coverage_respects_token_budget():
    documents = [Document(content="слово " * 200, meta={"rerank_score": 10.0 - index}) for index in range(4)]
    matrix = make_matrix(documents, [0.5] * 4)
    selected = select_protected_coverage(documents, top_k=4, token_budget=300, queries=["q0"], matrix=matrix, protected_top_p=1)
    from navigator.selection import token_count
    assert sum(token_count(item) for item in selected) <= 300


def test_protected_coverage_requires_matrix():
    with pytest.raises(ValueError):
        select_protected_coverage(make_documents([1.0]), top_k=1, token_budget=100, queries=["q0"], matrix={})


def test_protected_coverage_empty_documents():
    assert select_protected_coverage([], top_k=3, token_budget=100, queries=["q0"], matrix={"q0": []}) == []


def test_protected_coverage_registered_in_select_context():
    documents = make_documents([3.0, 2.0, 1.0])
    matrix = make_matrix(documents, [0.5, 0.4, 0.1])
    selected = select_context("protected_coverage", documents, 2, 10000, queries=["q0", "q1"], matrix=matrix)
    assert len(selected) == 2
    assert selected[0] == documents[0]
