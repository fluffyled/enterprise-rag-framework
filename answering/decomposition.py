"""Experimental planning and per-part extractive answering."""
from .core import generate, request_selection

PROMPT = '''Разбей вопрос сотрудника на самостоятельные вопросы для поиска по регламентам.
Каждая часть должна быть понятна без соседних частей. Повтори название процедуры или объекта.
Сохрани каждую явно запрошенную часть, включая сроки, роли, условия и согласования.
Если явно запрошена инструкция, выдели подготовку, подачу и запрошенные согласования.
Если вопрос простой, верни его дословно как одну часть. Не расширяй тему и не отвечай.
Верни JSON с полем questions, от одного до пяти коротких вопросов по-русски.'''
SCHEMA = {
    "type": "object",
    "properties": {"questions": {"type": "array", "minItems": 1, "maxItems": 5,
                                 "items": {"type": "string", "minLength": 1, "maxLength": 300}}},
    "required": ["questions"],
    "additionalProperties": False,
}


def generate_by_parts(question, fragments, endpoint):
    plan = request_selection(endpoint, {
        "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": question}],
        "temperature": 0, "seed": 42, "max_tokens": 400,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_object", "schema": SCHEMA},
    })
    questions = plan.get("questions") if isinstance(plan, dict) else None
    if not isinstance(questions, list) or not 1 <= len(questions) <= 5 or any(
        not isinstance(part, str) or not 1 <= len(part.strip()) <= 300 for part in questions
    ):
        raise ValueError("Некорректный план ответа")
    parts = [{"question": part, "result": generate(part, fragments, endpoint, whole_clauses=True)}
             for part in dict.fromkeys(part.strip() for part in questions)]
    statuses = {part["result"]["status"] for part in parts}
    if statuses == {"answered"}:
        status = "answered"
    elif "conflict" in statuses:
        status = "conflict"
    elif statuses & {"answered", "partial"}:
        status = "partial"
    elif "error" in statuses:
        status = "error"
    else:
        status = "insufficient"
    return {"status": status, "parts": parts}
