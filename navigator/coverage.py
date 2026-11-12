import numpy as np


def rank_normalize(raw_scores):
    raw = np.asarray(raw_scores, dtype=float)
    if not len(raw):
        return []
    order = np.argsort(-raw, kind="stable")
    normalized = np.zeros(len(raw), dtype=float)
    if len(raw) == 1:
        normalized[order[0]] = 1.0
    else:
        for rank, index in enumerate(order):
            normalized[index] = 1.0 - rank / (len(raw) - 1)
    return normalized.tolist()


def relevance_matrix(ranker, queries, documents, raw_cache=None):
    matrix = {}
    raw_matrix = {}
    raw_cache = raw_cache or {}
    for query in queries:
        raw = raw_cache.get(query)
        if raw is None:
            raw = ranker.predict([(query, document.content) for document in documents]) if ranker and documents else [document.meta.get("rrf_score", 0) or 0 for document in documents]
        raw_matrix[query] = [float(value) for value in raw]
        matrix[query] = rank_normalize(raw)
    return {"normalized_rank": matrix, "raw_cross_encoder": raw_matrix, "score_semantics": "rank normalization, not probability or sufficiency"}


def coverage_values(matrix, queries, documents, selected_indices):
    values = []
    for query_index, query in enumerate(queries):
        scores = matrix[query]
        values.append(max((scores[index] for index in selected_indices), default=0.0))
    return values
