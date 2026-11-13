import copy

from haystack import Document

from navigator.coverage import relevance_matrix
from navigator.query_analysis import Subtask
from navigator.retrieval import Retriever


class FakeRanker:
    def __init__(self):
        self.calls = []

    def predict(self, pairs):
        self.calls.append(pairs)
        return [(len(query) + len(text)) / 100 for query, text in pairs]


def test_coverage_cross_encoder_uses_one_equivalent_batch():
    documents = [Document(content="короткий текст"), Document(content="более длинный текст кандидата")]
    tasks = [Subtask("q0", "первая часть", {"start": 0, "end": 13}), Subtask("q1", "вторая часть", {"start": 14, "end": 26})]
    sequential = Retriever.__new__(Retriever)
    sequential.ranker = FakeRanker()
    expected = sequential._rerank("полный вопрос", copy.deepcopy(documents))
    raw = {"полный вопрос": [document.meta["rerank_score"] for document in expected]}
    for task in tasks:
        raw[task.text] = list(sequential.ranker.predict([(task.text, document.content) for document in expected]))
    expected_matrix = relevance_matrix(sequential.ranker, [task.text for task in tasks], expected, raw_cache=raw)

    batched = Retriever.__new__(Retriever)
    batched.ranker = FakeRanker()
    actual, actual_raw = batched._rerank_with_coverage("полный вопрос", copy.deepcopy(documents), tasks)
    actual_matrix = relevance_matrix(batched.ranker, [task.text for task in tasks], actual, raw_cache=actual_raw)

    assert len(batched.ranker.calls) == 1
    assert len(batched.ranker.calls[0]) == 6
    assert [document.id for document in actual] == [document.id for document in expected]
    assert [document.meta["rerank_score"] for document in actual] == [document.meta["rerank_score"] for document in expected]
    assert actual_raw == raw
    assert actual_matrix == expected_matrix
