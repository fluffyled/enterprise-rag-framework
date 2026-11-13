import re
import statistics


def normalize_text(text):
    return re.sub(r"\s+", " ", text or "").strip().lower()


def quote_supports_group(quote, group):
    quote = normalize_text(quote)
    for alternative in group.get("alternatives", []):
        gold = normalize_text(alternative.get("text"))
        if gold and (gold in quote or quote in gold):
            return True
        gold_tokens = set(re.findall(r"\w+", gold))
        quote_tokens = set(re.findall(r"\w+", quote))
        if gold_tokens and len(gold_tokens & quote_tokens) / len(gold_tokens) >= 0.8:
            return True
    return False


def selected_quotes(result):
    rows = []
    for field in ("answer", "steps"):
        for item in result.get(field, []):
            rows.append({"field": field, "source": item.get("source"), "quote": item.get("quote", "")})
    return rows


def evaluate_answer(result, case):
    groups = case.get("evidence_groups", [])
    quotes = selected_quotes(result)
    unique_quotes = list({(row["source"], normalize_text(row["quote"])): row for row in quotes}.values())
    supported = [any(quote_supports_group(row["quote"], group) for group in groups) for row in unique_quotes]
    group_hits = [any(quote_supports_group(row["quote"], group) for row in quotes) for group in groups]
    answerable = case.get("answerable", True)
    abstained = result.get("status") == "insufficient"
    citation_recall = sum(group_hits) / len(group_hits) if groups else None
    citation_precision = sum(supported) / len(supported) if supported else None
    correctness = bool(answerable and result.get("status") == "supported_quotes" and citation_recall == 1.0) if answerable else abstained
    return {
        "answer_correctness_proxy": correctness,
        "procedure_completeness": citation_recall if case.get("question_type") == "procedure" else None,
        "citation_precision_proxy": citation_precision,
        "citation_recall_proxy": citation_recall,
        "unsupported_quote_count": sum(not value for value in supported),
        "abstained": abstained,
        "literal_citation_validation": result.get("status") in ("supported_quotes", "insufficient"),
        "semantic_citation_review": None,
        "manual_answer_correctness": None,
        "manual_procedure_completeness": None,
        "manual_unsupported_claims": None,
        "review_status": "requires_human_review",
    }


def aggregate_answer_metrics(rows):
    answerable = [row for row in rows if row["answerable"]]
    unanswerable = [row for row in rows if not row["answerable"]]
    predicted_abstain = [row for row in rows if row["answer_metrics"]["abstained"]]
    true_abstain = [row for row in predicted_abstain if not row["answerable"]]
    missed_abstain = [row for row in unanswerable if not row["answer_metrics"]["abstained"]]

    def mean(key, source=rows):
        values = [row["answer_metrics"][key] for row in source if row["answer_metrics"].get(key) is not None]
        return statistics.fmean(values) if values else None

    return {
        "questions": len(rows),
        "answer_correctness_proxy": mean("answer_correctness_proxy", answerable),
        "procedure_completeness": mean("procedure_completeness"),
        "citation_precision_proxy": mean("citation_precision_proxy"),
        "citation_recall_proxy": mean("citation_recall_proxy", answerable),
        "unsupported_quote_count": sum(row["answer_metrics"]["unsupported_quote_count"] for row in rows),
        "abstention_precision": len(true_abstain) / len(predicted_abstain) if predicted_abstain else None,
        "abstention_recall": len(true_abstain) / len(unanswerable) if unanswerable else None,
        "false_abstentions": sum(row["answer_metrics"]["abstained"] for row in answerable),
        "missed_abstentions": len(missed_abstain),
        "end_to_end_success_rate": mean("answer_correctness_proxy"),
        "manual_review_required": True,
        "proxy_definition": "Correctness and citation metrics use overlap with annotated evidence quotes; they are not a substitute for semantic human review.",
    }


def failure_category(result, answer_metrics, candidate_all, context_all, answerable=True):
    if not answerable:
        return "missed_abstention"
    if not candidate_all:
        return "evidence_absent_from_candidates"
    if not context_all:
        return "evidence_not_selected"
    if result.get("status") == "error":
        return "generation_or_protocol_error"
    if answer_metrics["abstained"]:
        return "false_abstention"
    if answer_metrics.get("citation_recall_proxy") != 1.0:
        return "evidence_present_but_not_selected_by_llm"
    if answer_metrics.get("citation_precision_proxy") != 1.0:
        return "incorrect_or_extra_citations"
    if not answer_metrics["answer_correctness_proxy"]:
        return "incorrect_answer_with_available_evidence"
    return None
