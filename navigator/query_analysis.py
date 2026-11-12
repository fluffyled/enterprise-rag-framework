import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Subtask:
    id: str
    text: str
    source_span: dict


def decompose_question(question, max_parts=4):
    question = question.strip()
    original = [Subtask("q0", question, {"start": 0, "end": len(question)})]
    if len(question) < 45 or "Dialogue history:" in question:
        return original
    markers = list(re.finditer(r"\s+(?:а также|и)\s+|[;?]", question, flags=re.IGNORECASE))
    parts = []
    start = 0
    for marker in markers:
        end = marker.start()
        clause = question[start:end].strip(" ,—-")
        leading = start + len(question[start:end]) - len(question[start:end].lstrip(" ,—-"))
        if len(clause) >= 18 and re.search(r"\w{4}", clause):
            parts.append(Subtask(f"q{len(parts)}", clause, {"start": leading, "end": leading + len(clause)}))
        start = marker.end()
    clause = question[start:].strip(" ,—-")
    leading = start + len(question[start:]) - len(question[start:].lstrip(" ,—-"))
    if len(clause) >= 18:
        parts.append(Subtask(f"q{len(parts)}", clause, {"start": leading, "end": leading + len(clause)}))
    if len(parts) < 2:
        return original
    return parts[:max_parts]


def retrieval_queries(question, decompose=False):
    tasks = decompose_question(question) if decompose else [Subtask("q0", question, {"start": 0, "end": len(question)})]
    queries = [question]
    queries.extend(task.text for task in tasks if task.text != question)
    return list(dict.fromkeys(queries)), tasks
