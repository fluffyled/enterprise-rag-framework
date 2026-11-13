from collections import Counter

from .alignment import group_coverage, normalize_evidence_groups
from .metrics import latency_metrics


STAGES = ("bm25", "dense", "rrf", "cross_encoder", "selected_context")


def result_id(result):
    return result.get("chunk_id") or result.get("id")


def token_count(result):
    return len(result.get("content", "").split())


def select_oracle(candidates, case, token_budget=2000, top_k=6):
    groups = normalize_evidence_groups(case)
    selected = []
    coverages = []
    for group in groups:
        if not candidates:
            coverages.append(0.0)
            continue
        best = max(candidates, key=lambda result: group_coverage([result], group))
        coverage = group_coverage([best], group)
        if coverage > 0 and len(selected) < top_k and sum(token_count(item) for item in selected) + token_count(best) <= token_budget:
            selected.append(best)
            coverages.append(coverage)
        else:
            coverages.append(0.0)
    return {
        "evidence_recall": sum(value > 0 for value in coverages) / len(groups) if groups else None,
        "all_evidence_hit": float(bool(groups) and all(value > 0 for value in coverages)) if groups else None,
        "gold_span_coverage": sum(coverages) / len(groups) if groups else None,
        "selected_tokens": sum(token_count(item) for item in selected),
        "selected_ids": [result_id(item) for item in selected],
    }


def oracle_results(row, case, token_budget=2000):
    stages = row["trace"]["stages"]
    combined = []
    seen = set()
    for stage in ("bm25", "dense"):
        for result in stages.get(stage, []):
            if result_id(result) not in seen:
                seen.add(result_id(result))
                combined.append(result)
    return {
        "oracle_a_bm25_dense": select_oracle(combined, case, token_budget),
        "oracle_b_rrf": select_oracle(stages.get("rrf", []), case, token_budget),
        "oracle_c_reranked": select_oracle(stages.get("cross_encoder", []), case, token_budget),
    }


def direct_gold_oracle(case, token_budget=2000):
    candidates = []
    for group in normalize_evidence_groups(case):
        if not group["alternatives"]:
            continue
        gold = min(group["alternatives"], key=lambda span: span.end - span.start)
        candidates.append({"id": f"gold-{group['id']}", "chunk_id": f"gold-{group['id']}", "document_id": gold.document_id, "content": gold.text or "", "source_span": {"document_id": gold.document_id, "start": gold.start, "end": gold.end}})
    return {"oracle_d_direct_gold": select_oracle(candidates, case, token_budget)}


def classify_group(stable_row, group, chunks, token_budget=2000, sources=None):
    stages = stable_row["trace"]["stages"]
    values = {stage: group_coverage(stages.get(stage, []), group) for stage in STAGES}
    related_chunks = [chunk for chunk in chunks if any(chunk["meta"].get("document_id") == gold.document_id and chunk["meta"].get("source_span") and chunk["meta"]["source_span"]["start"] < gold.end and chunk["meta"]["source_span"]["end"] > gold.start for gold in group["alternatives"])]
    complete_chunk = any(group_coverage([{"document_id": chunk["meta"].get("document_id"), "source_span": chunk["meta"]["source_span"]}], group) >= 0.99 for chunk in related_chunks)
    parsing_error = False
    annotation_issue = False
    if sources is not None:
        for gold in group["alternatives"]:
            source = sources.get(gold.document_id)
            if source is None:
                annotation_issue = True
            elif gold.text and (gold.text not in source or source[gold.start:gold.end] != gold.text):
                parsing_error = True
    question = stable_row.get("question")
    decomposition_error = bool(question) and any(subtask["source_span"]["start"] < 0 or subtask["source_span"]["end"] > len(question) or question[subtask["source_span"]["start"]:subtask["source_span"]["end"]] != subtask["text"] for subtask in stable_row["trace"]["metadata"].get("subtasks", []))
    category = None
    if values["selected_context"] > 0:
        category = None
    elif parsing_error:
        category = "Parsing Error"
    elif decomposition_error:
        category = "Decomposition Error"
    elif annotation_issue:
        category = "Gold Annotation Issue"
    elif not related_chunks or not complete_chunk:
        category = "Chunking Error"
    elif values["bm25"] == 0 and values["dense"] == 0:
        category = "Candidate Retrieval Error"
    elif values["rrf"] == 0:
        category = "Fusion Error"
    elif values["cross_encoder"] == 0:
        category = "Reranking Error"
    else:
        category = "Selection Error"
    if category == "Selection Error" and stable_row["metrics"].get("selected_tokens", 0) >= token_budget:
        category = "Insufficient Context Budget"
    return {"group_id": group["id"], "category": category, "coverage_by_stage": values, "available_chunks": [chunk["id"] for chunk in related_chunks], "gold_spans": [{"document_id": gold.document_id, "start": gold.start, "end": gold.end, "characters": gold.end - gold.start} for gold in group["alternatives"]], "annotation_warning": any(gold.end - gold.start < 12 for gold in group["alternatives"])}


def analyze_reports(baseline_rows, stable_rows, cases, chunks, token_budget=2000, sources=None):
    baseline = {row["id"]: row for row in baseline_rows}
    stable = {row["id"]: row for row in stable_rows}
    case_by_id = {case["id"]: case for case in cases}
    query_rows = []
    errors = []
    oracle_counts = {"baseline": [], "stable": []}
    for query_id in sorted(baseline.keys() & stable.keys()):
        case = case_by_id[query_id]
        left, right = baseline[query_id], stable[query_id]
        baseline_recall = left["metrics"].get("evidence_recall@6")
        stable_recall = right["metrics"].get("evidence_recall@6")
        groups = normalize_evidence_groups(case)
        group_results = [classify_group(dict(right, question=case["question"]), group, chunks, token_budget, sources) for group in groups]
        errors.extend(error for error in group_results if error["category"])
        query_rows.append({
            "question_id": query_id,
            "question": case["question"],
            "answerable": case.get("answerable", True),
            "question_type": case.get("question_type"),
            "baseline_recall": baseline_recall,
            "stable_recall": stable_recall,
            "delta": stable_recall - baseline_recall if baseline_recall is not None and stable_recall is not None else None,
            "groups": group_results,
            "subtasks": right["trace"]["metadata"].get("subtasks", []),
            "selected_tokens": right["metrics"].get("selected_tokens"),
            "token_budget": token_budget,
        })
        if groups:
            oracle_counts["baseline"].append(oracle_results(left, case, token_budget))
            oracle_counts["stable"].append(oracle_results(right, case, token_budget))
    oracle_summary = {}
    for method, rows in oracle_counts.items():
        oracle_summary[method] = {}
        for oracle in ("oracle_a_bm25_dense", "oracle_b_rrf", "oracle_c_reranked"):
            oracle_summary[method][oracle] = latency_metrics([row[oracle]["evidence_recall"] for row in rows])
            oracle_summary[method][oracle]["all_evidence_hit"] = sum(row[oracle]["all_evidence_hit"] for row in rows) / len(rows) if rows else None
    direct_rows = [direct_gold_oracle(case, token_budget)["oracle_d_direct_gold"] for case in cases if normalize_evidence_groups(case)]
    oracle_summary["oracle_d_direct_gold"] = latency_metrics([row["evidence_recall"] for row in direct_rows])
    oracle_summary["oracle_d_direct_gold"]["all_evidence_hit"] = sum(row["all_evidence_hit"] for row in direct_rows) / len(direct_rows) if direct_rows else None
    return {
        "questions": query_rows,
        "errors": errors,
        "category_counts": dict(Counter(error["category"] for error in errors)),
        "stable_regressions": [row["question_id"] for row in query_rows if row["delta"] is not None and row["delta"] < 0],
        "oracle": oracle_summary,
        "token_budget": token_budget,
        "metrics_audit": {
            "fragment_mrr_ndcg": "reranked candidates before final context selector",
            "evidence_recall_at_6": "final selected context",
            "document_metrics": "deduplicated document ranking of candidates",
            "overlap_rule": "any positive character overlap counts as evidence hit; coverage separately measures fraction",
            "gold_used_online": False,
        },
    }
