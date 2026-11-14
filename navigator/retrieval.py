import copy
import hashlib
import json
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from haystack import Document
from haystack.components.joiners import DocumentJoiner
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever, InMemoryEmbeddingRetriever
from haystack.document_stores.in_memory import InMemoryDocumentStore
from .adaptive_retrieval import adaptive_analysis, local_query_plan, query_expansion
from .adaptive_strategy import choose_strategy
from .backends import create_embedding_backend, create_reranking_backend
from .bm25_fast import FastBM25
from .config import config_fingerprint, load_config, merge_config
from .contextual import prepare_contextual_chunks
from .coverage import relevance_matrix
from .graph import build_document_graph, expand_documents
from .parent_expansion import expand_parents, load_clause_store
from .query_analysis import retrieval_queries
from .selection import select_context
from .settings import DATA, INDEX, MODELS, ROOT
from .structure import enrich_hierarchy, profile_documents


def _model_lock_digest(backend="e5-small"):
    lock = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    role = "embedding" if backend == "e5-small" else "bge_m3"
    return hashlib.sha256(json.dumps(lock[role], sort_keys=True).encode()).hexdigest()


def _index_fingerprint(chunks, config):
    material = {
        "model_lock_sha256": _model_lock_digest(config["retrieval"]["embedding_backend"]),
        "config": config,
        "chunks": [{"id": chunk["id"], "content": chunk["content"], "meta": chunk.get("meta", {})} for chunk in chunks],
    }
    return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def build_index(config=None, chunks_path=None, index_path=None):
    config = load_config(config)
    chunks_path = Path(chunks_path) if chunks_path else DATA / "chunks.json"
    index_path = Path(index_path) if index_path else INDEX
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    hierarchy = None
    nodes = None
    if config["retrieval"]["hierarchical"] or config["retrieval"]["contextual"]:
        nodes = enrich_hierarchy(chunks)
    if config["retrieval"]["hierarchical"]:
        hierarchy = {"nodes": [node for node in nodes if node["type"] != "chunk"], "document_profiles": profile_documents(nodes, "document"), "section_profiles": profile_documents(nodes, "section")}
    graph = build_document_graph(chunks) if config["retrieval"]["graph_expansion"] else None
    prepare_contextual_chunks(chunks, nodes, config)
    model = create_embedding_backend(config["retrieval"]["embedding_backend"], device=config["retrieval"]["device"])
    texts = [x["content"] if config["retrieval"]["contextual"] else x["meta"]["name"] + " " + x["content"] for x in chunks]
    encoded = model.encode_documents_full(texts) if hasattr(model, "encode_documents_full") else {"dense_vecs": model.encode_documents(texts)}
    for index, (chunk, vector) in enumerate(zip(chunks, encoded["dense_vecs"])):
        chunk["embedding"] = vector.tolist()
        if encoded.get("lexical_weights") is not None:
            chunk["meta"]["bge_sparse"] = {str(token): float(weight) for token, weight in encoded["lexical_weights"][index].items()}
    if hierarchy:
        for level in ("document_profiles", "section_profiles"):
            profiles = hierarchy[level]
            vectors = model.encode_documents([x["meta"]["name"] + " " + x["content"] for x in profiles])
            for profile, vector in zip(profiles, vectors):
                profile["embedding"] = vector.tolist()
    payload = {
        "schema_version": 2,
        "model_lock_sha256": _model_lock_digest(config["retrieval"]["embedding_backend"]),
        "config_fingerprint": config_fingerprint(config),
        "index_fingerprint": _index_fingerprint(chunks, config),
        "config": config,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "documents": chunks,
        "hierarchy": hierarchy,
        "graph": graph,
    }
    index_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = index_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    tmp.replace(index_path)
    return len(chunks)


def document_snapshot(document, position=None):
    return {
        "id": document.id,
        "document_id": document.meta.get("document_id") or document.meta.get("relative_path") or document.meta.get("name"),
        "section_id": document.meta.get("section_id"),
        "chunk_id": document.meta.get("chunk_id") or document.id,
        "content": document.content,
        "original_content": document.meta.get("original_content", document.content),
        "source_span": document.meta.get("source_span"),
        "locator": document.meta.get("locator"),
        "score": document.score,
        "bm25_score": document.meta.get("bm25_score"),
        "dense_score": document.meta.get("dense_score"),
        "rrf_score": document.meta.get("rrf_score"),
        "rerank_score": document.meta.get("rerank_score"),
        "bge_sparse_score": document.meta.get("bge_sparse_score"),
        "late_interaction_score": document.meta.get("late_interaction_score"),
        "bge_fusion_score": document.meta.get("bge_fusion_score"),
        "final_position": position,
        "meta": copy.deepcopy(document.meta),
    }


class SearchResults(list):
    def __init__(self, documents=(), stages=None, timings=None, metadata=None):
        super().__init__(documents)
        self.stages = stages or {}
        self.timings = timings or {}
        self.metadata = metadata or {}

    def to_dict(self):
        return {"results": [document_snapshot(document, index + 1) for index, document in enumerate(self)], "stages": self.stages, "timings": self.timings, "metadata": self.metadata}


def _store(documents):
    store = InMemoryDocumentStore(embedding_similarity_function="cosine", bm25_algorithm="BM25Okapi")
    store.write_documents(documents)
    return store


def _join(document_lists, top_k):
    return DocumentJoiner(join_mode="reciprocal_rank_fusion", top_k=top_k).run(documents=document_lists)["documents"]


def _weighted_rank_fusion(dense, sparse, sparse_weight, top_k):
    scores = {}
    documents = {}
    for weight, ranking in ((1 - sparse_weight, dense), (sparse_weight, sparse)):
        for rank, document in enumerate(ranking):
            scores[document.id] = scores.get(document.id, 0.0) + weight / (60 + rank + 1)
            documents[document.id] = document
    merged = sorted(documents.values(), key=lambda document: scores[document.id], reverse=True)[:top_k]
    return [replace(document, score=scores[document.id]) for document in merged]


class Retriever:
    def __init__(self, rerank=None, config=None, index_path=None):
        self.config = load_config(config)
        self.index_path = Path(index_path) if index_path else INDEX
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        if config is None and payload.get("config"):
            self.config = load_config(payload["config"])
        if payload["model_lock_sha256"] != _model_lock_digest(self.config["retrieval"]["embedding_backend"]):
            raise RuntimeError("Ревизии моделей изменились: перестройте индекс")
        self.payload = payload
        documents = [Document(**document) for document in payload["documents"]]
        self.store = _store(documents)
        self.documents_by_chunk = {document.meta.get("chunk_id") or document.id: document for document in self.store.filter_documents()}
        self.model = create_embedding_backend(self.config["retrieval"]["embedding_backend"], device=self.config["retrieval"]["device"])
        use_reranker = self.config["retrieval"]["rerank"] if rerank is None else rerank
        self.ranker = create_reranking_backend(self.config["retrieval"]["reranker_backend"], device=self.config["retrieval"]["device"]) if use_reranker else None
        self.document_store = None
        self.section_store = None
        if payload.get("hierarchy"):
            self.document_store = _store([Document(**document) for document in payload["hierarchy"]["document_profiles"]])
            self.section_store = _store([Document(**document) for document in payload["hierarchy"]["section_profiles"]])
        from .manifest import validate as validate_manifest
        config_file = None
        if isinstance(config, (str, Path)):
            config_file = config
        elif isinstance(self.config, dict):
            config_file = None
        validate_manifest(config_path=config_file, index_path=self.index_path, strict=True)
        self._validate_index_config(self.config)
        self._configure_components(self.config)

    def _validate_index_config(self, config):
        indexed = self.payload.get("config", {}).get("retrieval", {})
        current = config["retrieval"]
        for key in ("chunk_words", "chunk_stride"):
            if key in indexed and indexed[key] != current[key]:
                raise RuntimeError(f"Изменён {key}: перестройте индекс")
        if indexed and indexed.get("contextual_mode", "off") != current["contextual_mode"]:
            raise RuntimeError("Изменено контекстное представление: перестройте индекс")
        index_backend = indexed.get("embedding_backend", "e5-small")
        same_backend = index_backend == current["embedding_backend"] or (index_backend.startswith("bge-m3-") and current["embedding_backend"].startswith("bge-m3-"))
        if not same_backend:
            raise RuntimeError("Изменён embedding backend: перестройте индекс")
        if indexed and indexed.get("device", "cpu") != current["device"]:
            raise RuntimeError("Изменено вычислительное устройство: перестройте индекс")
        if current["hierarchical"] and not self.payload.get("hierarchy"):
            raise RuntimeError("Индекс не содержит иерархию: перестройте его")
        if current["graph_expansion"] and not self.payload.get("graph"):
            raise RuntimeError("Индекс не содержит граф: перестройте его")

    def _configure_components(self, config):
        top_k = config["retrieval"]["candidate_top_k"]
        self.bm25 = InMemoryBM25Retriever(self.store, top_k=top_k)
        self.fast_bm25 = FastBM25(self.store.filter_documents())
        self.dense = InMemoryEmbeddingRetriever(self.store, top_k=top_k)
        self.join = DocumentJoiner(join_mode="reciprocal_rank_fusion", top_k=top_k)

    def _bge_sparse_search(self, lexical_weights, top_k):
        documents = []
        for document in self.store.filter_documents():
            weights = document.meta.get("bge_sparse", {})
            score = sum(float(weight) * float(weights.get(token, 0.0)) for token, weight in lexical_weights.items())
            if score > 0:
                clone = replace(copy.deepcopy(document), score=score)
                clone.meta["bge_sparse_score"] = score
                documents.append(clone)
        return sorted(documents, key=lambda document: document.score, reverse=True)[:top_k]

    def _hybrid_search(self, question, config, query_embedding=None):
        timings = {}
        started = time.perf_counter()
        bundle = self.model.encode_query_full(question) if self.model.supports_sparse else None
        if query_embedding is None:
            query_embedding = bundle["dense_vecs"][0].tolist() if bundle else self.model.encode_query(question)
        timings["embedding"] = time.perf_counter() - started
        started = time.perf_counter()
        if bundle:
            sparse = self._bge_sparse_search(bundle["lexical_weights"][0], config["retrieval"]["candidate_top_k"])
            timings["bm25"] = 0.0
            timings["bge_sparse"] = time.perf_counter() - started
        else:
            sparse = self.fast_bm25.search(question, config["retrieval"]["candidate_top_k"])
            timings["bm25"] = time.perf_counter() - started
        started = time.perf_counter()
        dense = self.dense.run(query_embedding=query_embedding)["documents"]
        timings["dense"] = time.perf_counter() - started
        for document in sparse:
            if bundle:
                document.meta["sparse_score"] = document.score
            else:
                document.meta["bm25_score"] = float(document.score) if document.score is not None else None
        for document in dense:
            document.meta["dense_score"] = float(document.score) if document.score is not None else None
            document.meta["cosine"] = float(document.score) if document.score is not None else None
        started = time.perf_counter()
        merged = _weighted_rank_fusion(dense, sparse, config["retrieval"]["bge_sparse_weight"], config["retrieval"]["candidate_top_k"]) if bundle else self.join.run(documents=[sparse, dense])["documents"]
        timings["rrf"] = time.perf_counter() - started
        for document in merged:
            document.meta["rrf_score"] = float(document.score) if document.score is not None else None
        return sparse, dense, merged, timings

    def _profile_search(self, store, question, query_embedding, top_k):
        sparse = InMemoryBM25Retriever(store, top_k=top_k).run(query=question)["documents"]
        dense = InMemoryEmbeddingRetriever(store, top_k=top_k).run(query_embedding=query_embedding)["documents"]
        return _join([sparse, dense], top_k)

    def _hierarchical_candidates(self, question, config, query_embedding):
        if self.document_store is None or self.section_store is None:
            raise RuntimeError("Индекс не содержит иерархию: перестройте его с hierarchical=true")
        top_k = config["retrieval"]["candidate_top_k"]
        document_candidates = self._profile_search(self.document_store, question, query_embedding, min(5, top_k))
        section_candidates = self._profile_search(self.section_store, question, query_embedding, min(10, top_k))
        selected_documents = {document.meta["document_id"] for document in document_candidates}
        selected_sections = {document.meta["section_id"] for document in section_candidates}
        for section in self.section_store.filter_documents():
            if section.meta["document_id"] in selected_documents:
                selected_sections.add(section.meta["section_id"])
        documents = [copy.deepcopy(document) for document in self.store.filter_documents() if document.meta.get("section_id") in selected_sections]
        if not documents:
            return [], [], []
        scoped_store = _store(documents)
        sparse = InMemoryBM25Retriever(scoped_store, top_k=top_k).run(query=question)["documents"]
        dense = InMemoryEmbeddingRetriever(scoped_store, top_k=top_k).run(query_embedding=query_embedding)["documents"]
        return _join([sparse, dense], top_k), document_candidates, section_candidates

    def _parent_expansion(self, documents, config):
        limit = config["retrieval"]["candidate_top_k"]
        expanded = list(documents)
        known = {document.id for document in expanded}
        for document in documents[:5]:
            related_ids = [document.meta.get("previous"), document.meta.get("next")]
            related = [chunk for chunk in self.documents_by_chunk.values() if chunk.meta.get("section_id") == document.meta.get("section_id")]
            if related:
                related_ids.extend([related[0].meta.get("chunk_id"), related[-1].meta.get("chunk_id")])
            for chunk_id in related_ids:
                related_document = self.documents_by_chunk.get(chunk_id)
                if related_document and related_document.id not in known and len(expanded) < limit:
                    clone = copy.deepcopy(related_document)
                    clone.meta["expanded_from"] = document.meta.get("chunk_id") or document.id
                    expanded.append(clone)
                    known.add(clone.id)
        return expanded

    def _late_interaction(self, question, documents, config):
        limit = config["retrieval"]["bge_late_interaction_top_n"]
        selected = documents[:limit]
        if not selected:
            return documents
        bundle = self.model.encode_query_full(question)
        query_vectors = bundle["colbert_vecs"][0] if isinstance(bundle["colbert_vecs"], list) else bundle["colbert_vecs"]
        scores = self.model.late_interaction_scores(query_vectors, selected)
        for document, score in zip(selected, scores):
            document.meta["late_interaction_score"] = score
        if config["retrieval"]["bge_fusion"] == "weighted_normalized":
            late_weight = config["retrieval"]["bge_late_weight"]
            rrf = [document.meta.get("rrf_score", document.score or 0) for document in selected]
            def normalize(values):
                low, high = min(values), max(values)
                return [(value - low) / (high - low) if high > low else 1.0 for value in values]
            for document, base_score, late_score in zip(selected, normalize(rrf), normalize(scores)):
                document.meta["bge_fusion_score"] = (1 - late_weight) * base_score + late_weight * late_score
            selected.sort(key=lambda document: document.meta["bge_fusion_score"], reverse=True)
        else:
            selected.sort(key=lambda document: document.meta["late_interaction_score"], reverse=True)
        return selected + documents[limit:]

    def _rerank(self, question, documents):
        documents = [replace(document, content=document.meta["original_content"]) if document.meta.get("original_content") is not None else document for document in documents]
        if self.ranker and documents:
            scores = self.ranker.predict([(question, document.content) for document in documents])
            for document, score in zip(documents, scores):
                document.meta["rerank_score"] = float(score)
            documents.sort(key=lambda document: document.meta["rerank_score"], reverse=True)
        return documents

    def _rerank_with_coverage(self, question, documents, tasks):
        documents = [replace(document, content=document.meta["original_content"]) if document.meta.get("original_content") is not None else document for document in documents]
        queries = list(dict.fromkeys([question] + [task.text for task in tasks]))
        pairs = [(query, document.content) for query in queries for document in documents]
        scores = self.ranker.predict(pairs)
        by_query = {}
        offset = 0
        for query in queries:
            by_query[query] = {document.id: float(score) for document, score in zip(documents, scores[offset:offset + len(documents)])}
            offset += len(documents)
        for document in documents:
            document.meta["rerank_score"] = by_query[question][document.id]
        documents.sort(key=lambda document: document.meta["rerank_score"], reverse=True)
        raw_cache = {query: [by_query[query][document.id] for document in documents] for query in queries}
        return documents, raw_cache

    def search(self, question, top_k=6, config=None):
        effective = load_config(merge_config(self.config, config or {}))
        self._validate_index_config(effective)
        self._configure_components(effective)
        settings = effective["retrieval"]
        total_started = time.perf_counter()
        extra_stages = {}
        if settings["hierarchical"]:
            started = time.perf_counter()
            query_embedding = self.model.encode_query(question)
            timings = {"embedding": time.perf_counter() - started}
            started = time.perf_counter()
            hierarchical, document_candidates, section_candidates = self._hierarchical_candidates(question, effective, query_embedding)
            timings["hierarchical_retrieval"] = time.perf_counter() - started
            extra_stages = {"documents": [document_snapshot(document, index + 1) for index, document in enumerate(document_candidates)], "sections": [document_snapshot(document, index + 1) for index, document in enumerate(section_candidates)], "hierarchical_chunks": [document_snapshot(document, index + 1) for index, document in enumerate(hierarchical)]}
            if settings["hierarchy_mode"] in ("fallback", "parent_expansion"):
                sparse, dense, global_merged, global_timings = self._hybrid_search(question, effective, query_embedding)
                for key in ("bm25", "dense", "rrf"):
                    timings[key] = global_timings[key]
                merged = _join([global_merged, hierarchical], settings["candidate_top_k"])
            else:
                sparse = dense = []
                merged = hierarchical
                timings.update({"bm25": 0.0, "dense": 0.0, "rrf": 0.0})
            if settings["hierarchy_mode"] == "parent_expansion":
                started = time.perf_counter()
                merged = self._parent_expansion(merged, effective)
                timings["parent_expansion"] = time.perf_counter() - started
        else:
            sparse, dense, merged, timings = self._hybrid_search(question, effective)
        metadata = {}
        selection_kwargs = {}
        tasks = []
        if settings["coverage_aware"]:
            started = time.perf_counter()
            adaptive_strategy = settings["selection_strategy"] == "adaptive_strategy"
            decomposed = settings["selection_strategy"] == "coverage_decomposed"
            queries, tasks = retrieval_queries(question, decompose=decomposed or adaptive_strategy, method=settings["decomposition_method"])
            timings["query_analysis"] = time.perf_counter() - started
            metadata["subtasks"] = [{"id": task.id, "text": task.text, "source_span": task.source_span, "depends_on": list(task.depends_on)} for task in tasks]
            metadata["decomposition_method"] = settings["decomposition_method"]
            if decomposed:
                started = time.perf_counter()
                known = {document.id for document in merged}
                expanded_limit = settings["candidate_top_k"] * len(queries)
                for subquery in queries[1:]:
                    _, _, additional, _ = self._hybrid_search(subquery, effective)
                    for document in additional:
                        if document.id not in known and len(merged) < expanded_limit:
                            merged.append(document)
                            known.add(document.id)
                timings["subtask_retrieval"] = time.perf_counter() - started
                metadata["candidate_limit_expanded"] = expanded_limit
        if settings["graph_expansion"]:
            if not self.payload.get("graph"):
                raise RuntimeError("Индекс не содержит граф: перестройте его с graph_expansion=true")
            started = time.perf_counter()
            seeds = list(dict.fromkeys(document.meta.get("document_id") or document.meta.get("relative_path") for document in merged[:5]))
            related = expand_documents(self.payload["graph"], seeds, settings["graph_depth"], settings["graph_relation_mode"])
            related_documents = [copy.deepcopy(document) for document in self.store.filter_documents() if (document.meta.get("document_id") or document.meta.get("relative_path")) in related]
            added = []
            if related_documents:
                related_store = _store(related_documents)
                related_sparse = InMemoryBM25Retriever(related_store, top_k=min(5, settings["candidate_top_k"])).run(query=question)["documents"]
                related_dense = InMemoryEmbeddingRetriever(related_store, top_k=min(5, settings["candidate_top_k"])).run(query_embedding=self.model.encode_query(question))["documents"]
                added = _join([related_sparse, related_dense], settings["candidate_top_k"])
            known = {document.id for document in merged}
            graph_limit = settings["candidate_top_k"] * (1 + len(related))
            for document in added:
                if document.id not in known and len(merged) < graph_limit:
                    merged.append(document)
                    known.add(document.id)
            timings["graph_expansion"] = time.perf_counter() - started
            metadata["graph"] = {"seed_documents": seeds, "related_documents": related, "added_candidates": len(added), "candidate_limit_expanded": graph_limit}
            extra_stages["graph_expansion"] = [document_snapshot(document, index + 1) for index, document in enumerate(added)]
        if self.model.supports_late_interaction:
            started = time.perf_counter()
            merged = self._late_interaction(question, merged, effective)
            timings["late_interaction"] = time.perf_counter() - started
            extra_stages["late_interaction"] = [document_snapshot(document, index + 1) for index, document in enumerate(merged)]
        sparse_stage = "bge_sparse" if self.model.supports_sparse else "bm25"
        stages = {sparse_stage: [document_snapshot(document, index + 1) for index, document in enumerate(sparse)], "dense": [document_snapshot(document, index + 1) for index, document in enumerate(dense)], "rrf": [document_snapshot(document, index + 1) for index, document in enumerate(merged)], **extra_stages}
        if self.model.supports_sparse:
            stages["bm25"] = []
        started = time.perf_counter()
        coverage_raw_cache = None
        if settings["coverage_aware"] and settings["batch_cross_encoder"] and not settings["adaptive"] and self.ranker and merged:
            reranked, coverage_raw_cache = self._rerank_with_coverage(question, list(merged), tasks)
        else:
            reranked = self._rerank(question, list(merged))
        timings["reranking"] = time.perf_counter() - started
        if settings["adaptive"]:
            analysis = adaptive_analysis(question, reranked, effective)
            metadata["adaptive"] = {"initial": analysis, "expanded": False, "expansion_queries": []}
            stages["initial_cross_encoder"] = [document_snapshot(document, index + 1) for index, document in enumerate(reranked)]
            if not analysis["sufficient"]:
                queries = local_query_plan(question) if settings["adaptive_mode"] == "query_planner" else query_expansion(question)
                queries = queries[:settings["adaptive_max_expansions"]]
                started = time.perf_counter()
                known = {document.id for document in merged}
                expanded_limit = settings["candidate_top_k"] * (1 + len(queries))
                for expanded_query in queries:
                    _, _, additional, _ = self._hybrid_search(expanded_query, effective)
                    for document in additional:
                        if document.id not in known and len(merged) < expanded_limit:
                            merged.append(document)
                            known.add(document.id)
                timings["adaptive_retrieval"] = time.perf_counter() - started
                started = time.perf_counter()
                reranked = self._rerank(question, list(merged))
                timings["reranking"] += time.perf_counter() - started
                metadata["adaptive"].update({"expanded": bool(queries), "expansion_queries": queries, "final": adaptive_analysis(question, reranked, effective), "candidate_limit_expanded": expanded_limit})
                stages["adaptive_expansion"] = [document_snapshot(document, index + 1) for index, document in enumerate(reranked)]
        if settings["coverage_aware"]:
            selection_kwargs = {"mmr_lambda": settings["mmr_lambda"], "coverage_lambda": settings["coverage_lambda"], "coverage_cost_normalization": settings["coverage_cost_normalization"], "coverage_document_diversity": settings["coverage_document_diversity"], "coverage_min_subtask": settings["coverage_min_subtask"], "protected_top_p": settings["protected_top_p"], "coverage_alpha": settings["coverage_alpha"], "coverage_beta": settings["coverage_beta"], "coverage_gamma": settings["coverage_gamma"]}
        if settings["coverage_aware"] and settings["selection_strategy"] in ("coverage", "coverage_decomposed", "protected_coverage"):
            coverage_started = time.perf_counter()
            matrix_queries = [task.text for task in tasks]
            raw_cache = coverage_raw_cache or {question: [document.meta.get("rerank_score", document.meta.get("rrf_score", 0) or 0) for document in reranked]}
            coverage = relevance_matrix(self.ranker, matrix_queries, reranked, raw_cache=raw_cache)
            selection_kwargs.update({"queries": matrix_queries, "matrix": coverage["normalized_rank"]})
            metadata["coverage_score_semantics"] = coverage["score_semantics"]
            metadata["raw_subtask_scores"] = coverage["raw_cross_encoder"]
            timings["reranking"] += time.perf_counter() - coverage_started
        stages["cross_encoder"] = [document_snapshot(document, index + 1) for index, document in enumerate(reranked)]
        if settings.get("multi_hop"):
            from .multi_hop import multi_hop_search
            selected = multi_hop_search(self, question, effective, metadata, timings)
            stages["multi_hop_context"] = [document_snapshot(document, index + 1) for index, document in enumerate(selected)]
            for index, document in enumerate(selected, 1):
                document.meta["final_position"] = index
            timings["total"] = time.perf_counter() - total_started
            return SearchResults(selected, stages, timings, metadata)
        started = time.perf_counter()
        strategy = settings["selection_strategy"]
        if strategy == "adaptive_strategy":
            decision = choose_strategy(question, tasks)
            strategy = decision["strategy"]
            metadata["adaptive_strategy"] = {**decision, "chosen_strategy": strategy}
            if strategy in ("coverage", "protected_coverage"):
                matrix_queries = [task.text for task in tasks]
                raw_cache = coverage_raw_cache or {question: [document.meta.get("rerank_score", document.meta.get("rrf_score", 0) or 0) for document in reranked]}
                coverage = relevance_matrix(self.ranker, matrix_queries, reranked, raw_cache=raw_cache)
                selection_kwargs.update({"queries": matrix_queries, "matrix": coverage["normalized_rank"]})
        selected = select_context(strategy, reranked, top_k, settings["context_token_budget"], **selection_kwargs) if settings["coverage_aware"] else reranked[:top_k]
        if settings.get("parent_expansion"):
            if not hasattr(self, "_clause_store"):
                self._clause_store = load_clause_store()
            selected, expansion_diag = expand_parents(selected, self._clause_store, settings["context_token_budget"], related_clauses=settings.get("related_clauses", False))
            metadata["parent_expansion"] = expansion_diag
        timings["context_selection"] = time.perf_counter() - started
        for index, document in enumerate(selected, 1):
            document.meta["final_position"] = index
        timings["total"] = time.perf_counter() - total_started
        stages["selected_context"] = [document_snapshot(document, index + 1) for index, document in enumerate(selected)]
        metadata.update({"config_fingerprint": config_fingerprint(effective), "index_fingerprint": self.payload.get("index_fingerprint", "legacy")})
        return SearchResults(selected, stages, timings, metadata)
