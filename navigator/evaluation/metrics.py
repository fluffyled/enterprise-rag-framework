import math
import random
import re
import statistics

import numpy as np

from .alignment import group_coverage, normalize_evidence_groups, result_document_id, result_relevance, result_span, selected_overlap_length


def unique_document_ranking(results):
    ranking = []
    seen = set()
    for result in results:
        document_id = result_document_id(result)
        if document_id and document_id not in seen:
            seen.add(document_id)
            ranking.append(document_id)
    return ranking


def dcg(relevances, k):
    return sum((2 ** float(value) - 1) / math.log2(index + 2) for index, value in enumerate(relevances[:k]))


def ndcg(ranked_ids, relevance, k):
    ideal = sorted(relevance.values(), reverse=True)[:k]
    denominator = dcg(ideal, k)
    return dcg([relevance.get(document_id, 0) for document_id in ranked_ids], k) / denominator if denominator else 0.0


def document_metrics(results, gold_document_ids, graded_relevance=None):
    gold = {str(value) for value in gold_document_ids}
    ranking = unique_document_ranking(results)
    relevance = {str(key): float(value) for key, value in (graded_relevance or {}).items()}
    if not relevance:
        relevance = {document_id: 1.0 for document_id in gold}
    metrics = {}
    for k in (1, 3, 5, 10):
        top = set(ranking[:k])
        hits = len(top & gold)
        metrics[f"document_hit@{k}"] = float(hits > 0) if gold else None
        metrics[f"document_recall@{k}"] = hits / len(gold) if gold else None
    metrics["all_documents_hit@5"] = float(gold.issubset(set(ranking[:5]))) if gold else None
    metrics["mrr@5"] = next((1.0 / (index + 1) for index, document_id in enumerate(ranking[:5]) if document_id in gold), 0.0) if gold else None
    metrics["ndcg@5"] = ndcg(ranking, relevance, 5) if gold else None
    metrics["document_mrr@10"] = next((1.0 / (index + 1) for index, document_id in enumerate(ranking[:10]) if document_id in gold), 0.0) if gold else None
    metrics["document_ndcg@10"] = ndcg(ranking, relevance, 10) if gold else None
    metrics["ranked_document_count"] = len(ranking)
    return metrics


def evidence_metrics(results, case):
    groups = normalize_evidence_groups(case)
    metrics = {}
    for k in (6, 20):
        coverages = [group_coverage(results[:k], group) for group in groups]
        metrics[f"evidence_recall@{k}"] = sum(value > 0 for value in coverages) / len(groups) if groups else None
        metrics[f"all_evidence_hit@{k}"] = float(bool(groups) and all(value > 0 for value in coverages)) if groups else None
        metrics[f"gold_span_coverage@{k}"] = sum(coverages) / len(groups) if groups else None
    relevances = [result_relevance(result, groups) for result in results]
    metrics["mrr@10"] = next((1.0 / (index + 1) for index, value in enumerate(relevances[:10]) if value > 0), 0.0) if groups else None
    metrics["ndcg@10"] = ndcg(list(range(len(results))), {index: value for index, value in enumerate(relevances) if value > 0}, 10) if groups else None
    metrics["gold_requirement_count"] = len(groups)
    return metrics


def token_set(text):
    return set(re.findall(r"\w+", text.lower(), flags=re.UNICODE))


def result_text(result):
    if isinstance(result, dict):
        return str(result.get("content", result.get("text", "")))
    return str(getattr(result, "content", ""))


def redundancy_ratio(results, threshold=0.8):
    redundant_tokens = 0
    total_tokens = 0
    previous = []
    for result in results:
        tokens = token_set(result_text(result))
        total_tokens += len(tokens)
        is_redundant = False
        for other in previous:
            union = tokens | other
            if union and len(tokens & other) / len(union) >= threshold:
                is_redundant = True
                break
        if is_redundant:
            redundant_tokens += len(tokens)
        previous.append(tokens)
    return redundant_tokens / total_tokens if total_tokens else 0.0


def context_metrics(results, case):
    groups = normalize_evidence_groups(case)
    selected_length = 0
    overlap_length = 0
    for result in results:
        span = result_span(result)
        if span:
            selected_length += span.end - span.start
            overlap_length += selected_overlap_length(result, groups)
    requirements = [group_coverage(results, group) for group in groups]
    return {
        "gold_span_coverage": sum(requirements) / len(groups) if groups else None,
        "covered_requirements": sum(value > 0 for value in requirements),
        "requirements_total": len(groups),
        "evidence_precision": overlap_length / selected_length if selected_length else None,
        "redundancy_ratio": redundancy_ratio(results),
        "unique_documents": len(set(unique_document_ranking(results))),
        "selected_characters": selected_length,
        "selected_tokens": sum(len(result_text(result).split()) for result in results),
    }


def per_query_metrics(results, case, selected_results=None):
    gold_documents = case.get("gold_document_ids")
    if gold_documents is None:
        gold_documents = sorted({span.document_id for group in normalize_evidence_groups(case) for span in group["alternatives"]})
    selected = results[:6] if selected_results is None else selected_results
    metrics = document_metrics(results, gold_documents, case.get("graded_relevance"))
    metrics.update(evidence_metrics(results, case))
    if selected_results is not None:
        selected_evidence = evidence_metrics(selected, case)
        for key in ("evidence_recall@6", "all_evidence_hit@6", "gold_span_coverage@6"):
            metrics[key] = selected_evidence[key]
    metrics.update(context_metrics(selected, case))
    return metrics


def aggregate_metrics(per_query):
    if not per_query:
        return {"questions": 0}
    keys = set().union(*(row.keys() for row in per_query))
    aggregate = {"questions": len(per_query)}
    for key in sorted(keys):
        values = [row[key] for row in per_query if isinstance(row.get(key), (int, float)) and not isinstance(row.get(key), bool)]
        if values:
            aggregate[key] = float(np.mean(values))
            aggregate[f"{key}_n"] = len(values)
    for key in ("all_evidence_hit@6", "all_documents_hit@5"):
        values = [row[key] for row in per_query if row.get(key) is not None]
        if values:
            aggregate[f"{key}_errors"] = sum(not value for value in values)
    return aggregate


def latency_metrics(values):
    values = [float(value) for value in values]
    if not values:
        return {}
    ordered = sorted(values)
    return {
        "n": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "mean": statistics.fmean(values),
        "p95": float(np.percentile(ordered, 95, method="linear")),
        "max": max(values),
    }


def paired_bootstrap(left, right, metric, iterations=2000, seed=42):
    if len(left) != len(right):
        raise ValueError("Для парного bootstrap нужны одинаковые запросы")
    pairs = [(a[metric], b[metric]) for a, b in zip(left, right) if a.get(metric) is not None and b.get(metric) is not None]
    if not pairs:
        return {"metric": metric, "n": 0, "difference": None}
    rng = random.Random(seed)
    observed = statistics.fmean(b - a for a, b in pairs)
    deltas = []
    for _ in range(iterations):
        sample = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        deltas.append(statistics.fmean(b - a for a, b in sample))
    return {
        "metric": metric,
        "n": len(pairs),
        "difference": observed,
        "ci95": [float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))],
        "iterations": iterations,
        "seed": seed,
    }
