from abc import ABC, abstractmethod

import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer

from .settings import MODELS


class EmbeddingBackend(ABC):
    supports_sparse = False
    supports_late_interaction = False

    @abstractmethod
    def encode_documents(self, texts):
        pass

    @abstractmethod
    def encode_query(self, query):
        pass


class E5SmallBackend(EmbeddingBackend):
    def __init__(self):
        self.model = SentenceTransformer(str(MODELS / "embedding"), device="cpu", local_files_only=True)

    def encode_documents(self, texts):
        return self.model.encode(["passage: " + text for text in texts], normalize_embeddings=True, batch_size=16, show_progress_bar=True)

    def encode_query(self, query):
        return self.model.encode("query: " + query, normalize_embeddings=True).tolist()


class BGEM3Backend(EmbeddingBackend):
    def __init__(self, mode="bge-m3-dense"):
        from FlagEmbedding import BGEM3FlagModel
        self.mode = mode
        self.supports_sparse = mode in ("bge-m3-sparse", "bge-m3-full")
        self.supports_late_interaction = mode in ("bge-m3-late", "bge-m3-full")
        self.model = BGEM3FlagModel(str(MODELS / "bge-m3"), devices="cpu", use_fp16=False, normalize_embeddings=True, batch_size=8, query_max_length=512, passage_max_length=512, return_dense=True, return_sparse=self.supports_sparse, return_colbert_vecs=self.supports_late_interaction)

    def encode_documents(self, texts):
        return self.model.encode_corpus(texts, return_dense=True, return_sparse=False, return_colbert_vecs=False)["dense_vecs"]

    def encode_documents_full(self, texts):
        return self.model.encode_corpus(texts, return_dense=True, return_sparse=self.supports_sparse, return_colbert_vecs=False)

    def encode_query(self, query):
        result = self.model.encode_queries(query, return_dense=True, return_sparse=False, return_colbert_vecs=False)
        dense = np.asarray(result["dense_vecs"])
        return (dense[0] if dense.ndim > 1 else dense).tolist()

    def encode_query_full(self, query):
        result = self.model.encode_queries(query, return_dense=True, return_sparse=self.supports_sparse, return_colbert_vecs=self.supports_late_interaction)
        dense = np.asarray(result["dense_vecs"])
        result["dense_vecs"] = dense.reshape(1, -1) if dense.ndim == 1 else dense
        if isinstance(result.get("lexical_weights"), dict):
            result["lexical_weights"] = [result["lexical_weights"]]
        return result

    def late_interaction_scores(self, query_vectors, documents):
        document_vectors = self.model.encode_corpus([document.content for document in documents], return_dense=False, return_sparse=False, return_colbert_vecs=True)["colbert_vecs"]
        query = np.asarray(query_vectors, dtype=np.float32)
        scores = []
        for document in document_vectors:
            passage = np.asarray(document, dtype=np.float32)
            similarity = query @ passage.T
            scores.append(float(similarity.max(axis=1).sum() / max(1, len(query))))
        return scores


class RerankingBackend(ABC):
    @abstractmethod
    def rerank(self, query, candidates):
        pass


class MiniLMRerankingBackend(RerankingBackend):
    def __init__(self):
        self.model = CrossEncoder(str(MODELS / "reranker"), device="cpu", local_files_only=True)

    def predict(self, pairs):
        return self.model.predict(pairs)

    def rerank(self, query, candidates):
        scores = self.predict([(query, candidate.content) for candidate in candidates])
        for candidate, score in zip(candidates, scores):
            candidate.meta["rerank_score"] = float(score)
        return sorted(candidates, key=lambda candidate: candidate.meta["rerank_score"], reverse=True)


def create_embedding_backend(name):
    if name == "e5-small":
        return E5SmallBackend()
    if name in ("bge-m3-dense", "bge-m3-sparse", "bge-m3-late", "bge-m3-full"):
        return BGEM3Backend(name)
    raise ValueError(f"Неизвестный embedding backend: {name}")


def create_reranking_backend(name):
    if name == "mminilm":
        return MiniLMRerankingBackend()
    raise ValueError(f"Неизвестный reranker backend: {name}")
