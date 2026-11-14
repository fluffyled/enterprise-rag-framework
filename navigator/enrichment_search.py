"""Поисковый канал обогащения (doc2query): ближайшие синтетические вопросы
и карточки фактов -> их исходные пункты подмешиваются в кандидаты multi-hop.

Эмбеддинги карточек считаются один раз и кэшируются (data/enrichment/
card_embeddings.npy) с fingerprint модели; смена модели/карточек сбрасывает кэш.
Карточки связаны с исходными пунктами через clause_id — сами по себе
доказательствами не являются, только ключами поиска.
"""

import hashlib
import json
import re
from pathlib import Path

import numpy as np

from .backends import create_embedding_backend
from .parent_expansion import load_clause_store

ROOT = Path(__file__).resolve().parent.parent
ENRICH_DIR = ROOT / "data/enrichment"
EMB_CACHE = ENRICH_DIR / "card_embeddings.npy"


def _norm(text):
    return re.sub(r"\s+", " ", text or " ").strip()


def _fact_text(card):
    parts = [card.get("action", ""), card.get("object", ""), card.get("deadline", ""), card.get("condition", "")]
    return _norm(" ".join(part for part in parts if part))


class EnrichmentIndex:
    """Векторный индекс синтетических вопросов и карточек фактов."""

    def __init__(self, model=None):
        self.model = model or create_embedding_backend("bge-m3-sparse", device="cuda")
        self.questions = [json.loads(line) for line in (ENRICH_DIR / "synthetic_questions.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.facts = [json.loads(line) for line in (ENRICH_DIR / "fact_cards.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        question_texts = [row["question"] for row in self.questions]
        fact_texts = [_fact_text(card) for card in self.facts]
        lock = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
        fingerprint = hashlib.sha256(json.dumps(lock["bge_m3"], sort_keys=True).encode()).hexdigest()[:16]
        material = hashlib.sha256(("\n".join(question_texts + fact_texts)).encode("utf-8")).hexdigest()[:16]
        cache_key = f"{fingerprint}:{material}"
        if EMB_CACHE.exists():
            payload = np.load(EMB_CACHE, allow_pickle=True).item()
            if payload.get("key") == cache_key:
                self.matrix = payload["matrix"]
                self.entries = payload["entries"]
                return
        texts = [("[Q] " + text) for text in question_texts] + [("[F] " + text) for text in fact_texts]
        result = self.model.model.encode_queries(texts, return_dense=True, return_sparse=False, return_colbert_vecs=False)
        self.matrix = np.asarray(result["dense_vecs"], dtype=np.float32)
        norms = np.linalg.norm(self.matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1e-9
        self.matrix = self.matrix / norms
        self.entries = [("question", index) for index in range(len(self.questions))] + [("fact", index) for index in range(len(self.facts))]
        EMB_CACHE.parent.mkdir(parents=True, exist_ok=True)
        np.save(EMB_CACHE, {"key": cache_key, "matrix": self.matrix, "entries": self.entries})

    def search(self, question, top_k=10, include_facts=True):
        query = np.array(self.model.encode_query(question), dtype=np.float32)
        scores = self.matrix @ query / (np.linalg.norm(self.matrix, axis=1) * (np.linalg.norm(query) + 1e-9))
        ranked = np.argsort(-scores)
        clause_ids = []
        for position in ranked:
            kind, index = self.entries[position]
            if kind == "fact" and not include_facts:
                continue
            row = self.questions[index] if kind == "question" else self.facts[index]
            clause_id = row["clause_id"]
            if clause_id not in clause_ids:
                clause_ids.append(clause_id)
            if len(clause_ids) >= top_k:
                break
        return clause_ids


def clause_documents(retriever, clause_ids, store=None):
    """Документы-полные пункты для подмешивания в кандидаты."""
    store = store or load_clause_store()
    documents = []
    for clause_id in clause_ids:
        for key, entry in store.items():
            for clause in entry["clauses"]:
                if clause["clause_id"] != clause_id:
                    continue
                documents.append({
                    "clause": clause,
                    "document": entry["document_id"],
                    "sha": entry.get("sha256", key),
                })
                break
    from haystack import Document
    return [
        Document(content=item["clause"]["full_text"], meta={
            "document_id": item["document"],
            "name": item["document"],
            "sha256": item["sha"],
            "chunk_id": f"enrich-{item['clause']['clause_id']}",
            "clause_id": item["clause"]["clause_id"],
            "clause_number": item["clause"]["number"],
            "source_span": {"document_id": item["document"], "start": item["clause"]["start"], "end": item["clause"]["end"]},
            "rerank_score": 0.0,
        })
        for item in documents
    ]
