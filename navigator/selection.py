import re


def token_count(document):
    return len(re.findall(r"\w+|[^\w\s]", document.content, flags=re.UNICODE))


def tokens(document):
    return set(re.findall(r"\w+", document.content.lower(), flags=re.UNICODE))


def similarity(left, right):
    a, b = tokens(left), tokens(right)
    return len(a & b) / len(a | b) if a | b else 0.0


def fits(document, selected, budget):
    return sum(token_count(item) for item in selected) + token_count(document) <= budget


def select_top_k(documents, top_k, token_budget, **kwargs):
    selected = []
    for document in documents:
        if len(selected) < top_k and fits(document, selected, token_budget):
            selected.append(document)
    return selected


def select_deduplicated(documents, top_k, token_budget, threshold=0.8, **kwargs):
    selected = []
    for document in documents:
        if any(similarity(document, existing) >= threshold for existing in selected):
            continue
        if fits(document, selected, token_budget):
            selected.append(document)
        if len(selected) == top_k:
            break
    return selected


def select_mmr(documents, top_k, token_budget, mmr_lambda=0.7, **kwargs):
    selected = []
    remaining = list(documents)
    if not remaining:
        return []
    raw = [document.meta.get("rerank_score", document.score or 0) for document in documents]
    minimum, maximum = min(raw), max(raw)
    normalized = {document.id: (value - minimum) / (maximum - minimum) if maximum > minimum else 1.0 for document, value in zip(documents, raw)}
    while remaining and len(selected) < top_k:
        def score(document):
            redundancy = max((similarity(document, existing) for existing in selected), default=0.0)
            return mmr_lambda * normalized[document.id] - (1 - mmr_lambda) * redundancy
        document = max(remaining, key=score)
        remaining.remove(document)
        if fits(document, selected, token_budget):
            selected.append(document)
    return selected


def select_coverage(documents, top_k, token_budget, queries, matrix, coverage_lambda=0.15, coverage_cost_normalization=True, coverage_document_diversity=0.0, coverage_min_subtask=False, **kwargs):
    selected = []
    selected_indices = []
    remaining = list(enumerate(documents))
    current_coverage = [0.0] * len(queries)
    if coverage_min_subtask:
        for query_index, query in enumerate(queries):
            feasible = [(index, document) for index, document in remaining if len(selected) < top_k and fits(document, selected, token_budget)]
            if not feasible:
                break
            index, document = max(feasible, key=lambda item: matrix[query][item[0]])
            if matrix[query][index] <= 0:
                continue
            selected.append(document)
            selected_indices.append(index)
            current_coverage = [max(current, matrix[queries[item]][index]) for item, current in enumerate(current_coverage)]
            remaining = [(candidate_index, candidate) for candidate_index, candidate in remaining if candidate_index != index]
    while remaining and len(selected) < top_k:
        best = None
        best_gain = 0.0
        for index, document in remaining:
            if not fits(document, selected, token_budget):
                continue
            gains = []
            for query_index, query in enumerate(queries):
                score = matrix[query][index]
                gains.append(max(current_coverage[query_index], score) - current_coverage[query_index])
            coverage_gain = sum(gains) / len(queries)
            redundancy = sum(similarity(document, selected_document) for selected_document in selected) / max(1, len(selected))
            document_id = document.meta.get("document_id") or document.meta.get("relative_path") or document.meta.get("name")
            known_documents = {item.meta.get("document_id") or item.meta.get("relative_path") or item.meta.get("name") for item in selected}
            diversity_bonus = coverage_document_diversity if document_id not in known_documents else 0.0
            cost = max(0.05, token_count(document) / token_budget) if coverage_cost_normalization else 1.0
            gain = (coverage_gain - coverage_lambda * redundancy + diversity_bonus) / cost
            if gain > best_gain:
                best_gain = gain
                best = (index, document, gains)
        if best is None:
            for index, document in remaining:
                if fits(document, selected, token_budget):
                    best = (index, document, [0.0] * len(queries))
                    break
        if best is None:
            break
        index, document, gains = best
        selected.append(document)
        selected_indices.append(index)
        current_coverage = [current + gain for current, gain in zip(current_coverage, gains)]
        remaining = [(candidate_index, candidate) for candidate_index, candidate in remaining if candidate_index != index]
    if not selected and documents:
        return select_top_k(documents, top_k, token_budget)
    return selected


def select_protected_coverage(documents, top_k, token_budget, queries, matrix, protected_top_p=2, coverage_alpha=0.5, coverage_beta=0.3, coverage_gamma=0.2, **kwargs):
    if not documents:
        return []
    if not queries or not matrix:
        raise ValueError("protected_coverage требует queries и matrix")
    raw = [document.meta.get("rerank_score", document.score or 0) for document in documents]
    minimum, maximum = min(raw), max(raw)
    relevance = {document.id: (value - minimum) / (maximum - minimum) if maximum > minimum else 1.0 for document, value in zip(documents, raw)}

    selected = []
    selected_indices = []
    remaining = list(enumerate(documents))
    for index, document in remaining[:max(0, min(protected_top_p, len(remaining)))]:
        if fits(document, selected, token_budget) and len(selected) < top_k:
            selected.append(document)
            selected_indices.append(index)
    protected_ids = {id(document) for document in selected}
    remaining = [(index, document) for index, document in remaining if id(document) not in protected_ids]
    current_coverage = [max((matrix[query][index] for index in selected_indices), default=0.0) for query in queries]
    while remaining and len(selected) < top_k:
        best = None
        best_score = None
        for index, document in remaining:
            if not fits(document, selected, token_budget):
                continue
            coverage_gain = sum(max(0.0, matrix[query][index] - current_coverage[query_index]) for query_index, query in enumerate(queries)) / len(queries)
            redundancy = sum(similarity(document, existing) for existing in selected) / max(1, len(selected))
            score = coverage_alpha * relevance[document.id] + coverage_beta * coverage_gain - coverage_gamma * redundancy
            if best_score is None or score > best_score:
                best_score = score
                best = (index, document)
        if best is None:
            break
        selected.append(best[1])
        selected_indices.append(best[0])
        remaining.remove(best)
        current_coverage = [max(current, matrix[query][best[0]]) for current, query in zip(current_coverage, queries)]
    return selected


def select_context(strategy, documents, top_k, token_budget, **kwargs):
    selectors = {"top_k": select_top_k, "deduplicated": select_deduplicated, "mmr": select_mmr, "coverage": select_coverage, "coverage_decomposed": select_coverage, "protected_coverage": select_protected_coverage}
    if strategy not in selectors:
        raise ValueError(f"Неизвестная стратегия выбора: {strategy}")
    return selectors[strategy](documents, top_k, token_budget, **kwargs)
