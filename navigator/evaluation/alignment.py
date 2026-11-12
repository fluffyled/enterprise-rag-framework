from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSpan:
    document_id: str
    start: int
    end: int
    text: str | None = None

    def __post_init__(self):
        if not self.document_id:
            raise ValueError("У gold span отсутствует document_id")
        if self.start < 0 or self.end <= self.start:
            raise ValueError("Некорректный символьный интервал")


def normalize_evidence_groups(case):
    groups = case.get("evidence_groups")
    if groups is None:
        spans = case.get("gold_spans") or []
        groups = [{"id": "evidence", "alternatives": spans}] if spans else []
    normalized = []
    for index, group in enumerate(groups):
        alternatives = group.get("alternatives", group.get("spans", []))
        spans = [SourceSpan(**{key: span[key] for key in ("document_id", "start", "end", "text") if key in span}) for span in alternatives]
        normalized.append({"id": str(group.get("id", index)), "alternatives": spans, "requirement": group.get("requirement")})
    return normalized


def result_document_id(result):
    if isinstance(result, dict):
        return str(result.get("document_id") or result.get("meta", {}).get("document_id") or result.get("meta", {}).get("relative_path") or result.get("meta", {}).get("name") or result.get("id"))
    meta = getattr(result, "meta", {})
    return str(meta.get("document_id") or meta.get("relative_path") or meta.get("name") or getattr(result, "id", ""))


def result_span(result):
    if isinstance(result, dict):
        span = result.get("source_span") or result.get("meta", {}).get("source_span")
        document_id = result_document_id(result)
        content = result.get("content", result.get("text", ""))
    else:
        meta = getattr(result, "meta", {})
        span = meta.get("source_span")
        document_id = result_document_id(result)
        content = getattr(result, "content", "")
    if not span:
        return None
    if isinstance(span, dict):
        start, end = span.get("start"), span.get("end")
        document_id = str(span.get("document_id") or document_id)
    else:
        start, end = span
    if start is None or end is None:
        return None
    return SourceSpan(document_id, int(start), int(end), content)


def intersection_length(left, right):
    if left.document_id != right.document_id:
        return 0
    return max(0, min(left.end, right.end) - max(left.start, right.start))


def coverage(left, right):
    return intersection_length(left, right) / max(1, right.end - right.start)


def group_coverage(results, group):
    best = 0.0
    for result in results:
        retrieved = result_span(result)
        if retrieved is None:
            continue
        for gold in group["alternatives"]:
            best = max(best, coverage(retrieved, gold))
            if best == 1.0:
                return best
    return best


def result_relevance(result, groups):
    retrieved = result_span(result)
    if retrieved is None:
        return 0.0
    best = 0.0
    for group in groups:
        for gold in group["alternatives"]:
            best = max(best, coverage(retrieved, gold))
    return best


def merged_intervals(intervals):
    if not intervals:
        return []
    ordered = sorted(intervals)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def selected_overlap_length(result, groups):
    retrieved = result_span(result)
    if retrieved is None:
        return 0
    intervals = []
    for group in groups:
        for gold in group["alternatives"]:
            if gold.document_id != retrieved.document_id:
                continue
            start, end = max(retrieved.start, gold.start), min(retrieved.end, gold.end)
            if end > start:
                intervals.append((start, end))
    return sum(end - start for start, end in merged_intervals(intervals))
