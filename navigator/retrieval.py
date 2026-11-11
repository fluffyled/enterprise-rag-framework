import json
from pathlib import Path
import numpy as np
from haystack import Document
from haystack.document_stores.in_memory import InMemoryDocumentStore
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever, InMemoryEmbeddingRetriever
from haystack.components.joiners import DocumentJoiner
from sentence_transformers import SentenceTransformer, CrossEncoder
from .settings import DATA, MODELS, INDEX


def build_index():
    chunks = json.loads((DATA / "chunks.json").read_text(encoding="utf-8"))
    model = SentenceTransformer(str(MODELS / "embedding"), device="cpu", local_files_only=True)
    vectors = model.encode(["passage: " + x["meta"]["name"] + " " + x["content"] for x in chunks], normalize_embeddings=True, batch_size=16, show_progress_bar=True)
    for x, v in zip(chunks, vectors): x["embedding"] = v.tolist()
    import hashlib
    lock = Path(__file__).resolve().parent.parent / "models.lock.json"
    payload = {"model_lock_sha256": hashlib.sha256(json.dumps(json.loads(lock.read_text())["embedding"], sort_keys=True).encode()).hexdigest(), "documents": chunks}
    tmp = INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(INDEX)
    return len(chunks)


class Retriever:
    def __init__(self, rerank=True):
        import hashlib
        payload = json.loads(INDEX.read_text(encoding="utf-8"))
        lock = Path(__file__).resolve().parent.parent / "models.lock.json"
        if payload["model_lock_sha256"] != hashlib.sha256(json.dumps(json.loads(lock.read_text())["embedding"], sort_keys=True).encode()).hexdigest():
            raise RuntimeError("Ревизии моделей изменились: перестройте индекс")
        self.store = InMemoryDocumentStore(embedding_similarity_function="cosine", bm25_algorithm="BM25Okapi")
        self.store.write_documents([Document(**d) for d in payload["documents"]])
        self.model = SentenceTransformer(str(MODELS / "embedding"), device="cpu", local_files_only=True)
        self.ranker = CrossEncoder(str(MODELS / "reranker"), device="cpu", local_files_only=True) if rerank else None
        self.bm25 = InMemoryBM25Retriever(self.store, top_k=20)
        self.dense = InMemoryEmbeddingRetriever(self.store, top_k=20)
        self.join = DocumentJoiner(join_mode="reciprocal_rank_fusion", top_k=20)

    def search(self, question, top_k=6):
        q = self.model.encode("query: " + question, normalize_embeddings=True).tolist()
        sparse = self.bm25.run(query=question)["documents"]
        dense = self.dense.run(query_embedding=q)["documents"]
        cosine = {d.id: d.score for d in dense}
        merged = self.join.run(documents=[sparse, dense])["documents"]
        if self.ranker and merged:
            scores = self.ranker.predict([(question, d.content) for d in merged])
            for d, s in zip(merged, scores): d.meta["rerank_score"] = float(s)
            merged.sort(key=lambda d: d.meta["rerank_score"], reverse=True)
        for d in merged: d.meta["cosine"] = cosine.get(d.id)
        return merged[:top_k]
