import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Subtask:
    id: str
    text: str
    source_span: dict
    context: str | None = None
    depends_on: tuple[str, ...] = ()


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


def retrieval_queries(question, decompose=False, method="existing"):
    if method == "improved":
        tasks = decompose_question_improved(question)
    elif method == "planner":
        tasks = local_llm_decompose(question)
    else:
        tasks = decompose_question(question) if decompose else [Subtask("q0", question, {"start": 0, "end": len(question)})]
    queries = [question]
    queries.extend(task.text for task in tasks if task.text != question)
    return list(dict.fromkeys(queries)), tasks


def decompose_question_improved(question, max_parts=4):
    question = question.strip()
    original = [Subtask("q0", question, {"start": 0, "end": len(question)}, context=question)]
    if len(question) < 30 or "Dialogue history:" in question:
        return original
    marker_pattern = r"\s+(?:а также|и)\s+|[;?]|,(?=\s*(?:как|какой|кого|кто|когда|сколько|назовите|укажите)\b)"
    list_question = bool(
        re.search(r"\b(?:назовите|перечислите|укажите)\b", question, flags=re.IGNORECASE)
        or question.count(",") >= 2
        or re.search(r",(?!\s*(?:как|какой|какие|кого|кто|где|что|когда|сколько|если|при\b))\s*[^,]+\s+и\s+", question, flags=re.IGNORECASE)
    )
    if list_question:
        marker_pattern += r"|,"
    markers = list(re.finditer(marker_pattern, question, flags=re.IGNORECASE))
    parts = []
    start = 0
    for marker in markers:
        raw = question[start:marker.start()]
        clause = raw.strip(" ,—-")
        leading = start + len(raw) - len(raw.lstrip(" ,—-"))
        predicate = re.search(r"\b(?:как|какой|какие|кого|кто|где|что|когда|сколько|назовите|укажите|пода|утверж|направ|заполня|проверя|заключа|освобожда|оформля|получа|использу)\w*", clause, flags=re.IGNORECASE)
        min_chars = 4 if list_question else 8
        if len(clause) >= min_chars and len(clause.split()) >= (1 if list_question else 2) and (predicate or len(parts) > 0):
            depends = (parts[-1].id,) if parts and re.search(r"\b(?:если|при условии|при наличии)\b", clause, flags=re.IGNORECASE) else ()
            parts.append(Subtask(f"q{len(parts)}", clause, {"start": leading, "end": leading + len(clause)}, context=question, depends_on=depends))
        start = marker.end()
    raw = question[start:]
    clause = raw.strip(" ,—-")
    leading = start + len(raw) - len(raw.lstrip(" ,—-"))
    if len(clause) >= (4 if list_question else 15) and len(clause.split()) >= (1 if list_question else 3):
        depends = (parts[-1].id,) if parts and re.search(r"\b(?:если|при условии|при наличии)\b", clause, flags=re.IGNORECASE) else ()
        parts.append(Subtask(f"q{len(parts)}", clause, {"start": leading, "end": leading + len(clause)}, context=question, depends_on=depends))
    if len(parts) < 2:
        return original
    return parts[:max_parts]


def local_llm_decompose(question, endpoint=None, timeout=90, with_status=False):
    import json
    import os
    import urllib.parse
    import urllib.request
    endpoint = endpoint or os.environ.get("LLM_ENDPOINT", "http://127.0.0.1:8080/v1/chat/completions")
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1", "llm"):
        raise ValueError("Planner разрешён только на локальном endpoint")
    item_schema = {"type": "object", "properties": {"text": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, "required": ["text", "start", "end"], "additionalProperties": False}
    schema = {"type": "object", "properties": {"subtasks": {"type": "array", "items": item_schema, "maxItems": 4}}, "required": ["subtasks"], "additionalProperties": False}
    payload = {"messages": [{"role": "system", "content": "Split the question into at most four independently retrievable requirements. Return exact character spans from the original question. Do not paraphrase, answer or add facts. Return original whole question as one subtask when decomposition is unnecessary."}, {"role": "user", "content": question}], "temperature": 0, "max_tokens": 300, "response_format": {"type": "json_object", "schema": schema}}
    try:
        request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content = json.load(response)["choices"][0]["message"]["content"]
        rows = json.loads(content)["subtasks"]
        tasks = []
        for index, row in enumerate(rows[:4]):
            start, end = row["start"], row["end"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(question) or question[start:end] != row["text"]:
                raise ValueError("Planner вернул неextractive span")
            tasks.append(Subtask(f"q{index}", row["text"], {"start": start, "end": end}, context=question))
        if not tasks:
            raise ValueError("Пустой planner result")
        return (tasks, "planner") if with_status else tasks
    except Exception:
        tasks = decompose_question_improved(question)
        return (tasks, "fallback") if with_status else tasks
