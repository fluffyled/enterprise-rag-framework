import numpy as np
from types import SimpleNamespace

from navigator.backends import BGEM3Backend


class FakeM3:
    def encode_queries(self, query, **kwargs):
        return {"dense_vecs": np.array([1.0, 0.0]), "lexical_weights": {"1": np.float32(0.5)}, "colbert_vecs": np.eye(2)}


def test_single_query_shapes_are_normalized():
    backend = BGEM3Backend.__new__(BGEM3Backend)
    backend.model = FakeM3()
    result = backend.encode_query_full("q")
    assert result["dense_vecs"].shape == (1, 2)
    assert isinstance(result["lexical_weights"], list)
    assert backend.encode_query("q") == [1.0, 0.0]


def test_late_interaction_maxsim():
    backend = BGEM3Backend.__new__(BGEM3Backend)
    backend.model = SimpleNamespace(encode_corpus=lambda texts, **kwargs: {"colbert_vecs": [np.eye(2)]})
    scores = backend.late_interaction_scores(np.eye(2), [SimpleNamespace(content="x")])
    assert scores == [1.0]


def test_bge_reranker_backend_registered():
    from navigator.backends import create_reranking_backend

    assert create_reranking_backend.__module__ == "navigator.backends"


def test_bge_reranker_sorts_by_score():
    from types import SimpleNamespace

    from haystack import Document

    from navigator.backends import BgeV2M3RerankingBackend

    backend = BgeV2M3RerankingBackend.__new__(BgeV2M3RerankingBackend)
    backend.model = SimpleNamespace(predict=lambda pairs: [0.1 * index for index, _ in enumerate(pairs)])
    candidates = [Document(content="a"), Document(content="b"), Document(content="c")]
    result = backend.rerank("q", list(candidates))
    assert [document.content for document in result] == ["c", "b", "a"]
    assert all(document.meta["rerank_score"] is not None for document in result)
