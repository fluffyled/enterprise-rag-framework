"""Проверяемая генерация (H5, этап 7 ТЗ).

Вместо выбора обрывков предложений: evidence blocks → структурированный план
ответа → детерминированная верификация каждого шага → понятный ответ.

1. Блоки: документ, пункт, полный текст, уникальный ID.
2. LLM формирует план: steps[{action, actor, condition, deadline, evidence_id}],
   missing_information[].
3. Верификация (детерминированная): evidence_id существует; ключевые токены
   действия присутствуют в тексте блока (поддержка ≥ порога); срок/условие не
   выдуманы (проверяются на вхождение в блок). Неподдержанные шаги отбрасываются
   в missing_information, а не в ответ.
4. Ответ: поддержанные шаги с дословными цитатами блоков; если поддержанных
   шагов нет — insufficient (отказ). Частичная поддержка — явный список
   недостающего.
"""

import json
import re
import urllib.request

from .parent_expansion import token_count_text

PLAN_PROMPT = """Ты составляешь план ответа строго по предоставленным блокам доказательств. Каждый блок имеет id, документ, пункт и полный текст. Ответь JSON: {"steps": [{"action": "что сделать", "actor": "кто действует", "condition": "когда применимо", "deadline": "срок", "evidence_id": "id блока"}], "missing_information": ["чего блоки не покрывают"]}. Правила: отвечай на русском языке; actor/condition/deadline — пустые строки, если не указаны в блоке; каждый шаг должен ссылаться на блок, который его прямо подтверждает; не используй внешние знания; не выдумывай сроки, участников и условия; если блоки не покрывают часть вопроса — укажи это в missing_information; шаги в логическом порядке; 1-6 шагов."""

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {"type": "array", "maxItems": 8, "items": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "actor": {"type": "string"},
                "condition": {"type": "string"},
                "deadline": {"type": "string"},
                "evidence_id": {"type": "string"},
            },
            "required": ["action", "evidence_id"],
            "additionalProperties": False,
        }},
        "missing_information": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["steps", "missing_information"],
    "additionalProperties": False,
}

SUPPORT_TOKEN_THRESHOLD = 0.5


def _tokens(text):
    """Стеммированные токены (первые 5 символов) — устойчивы к русским
    словоформам («подать»/«подаётся» -> «подат»/«подаё»)."""
    return {token[:5] for token in re.findall(r"\w+", (text or "").lower()) if len(token) >= 3}


def _digits(text):
    return set(re.findall(r"\d+", text or ""))


def build_evidence_blocks(documents, char_cap=5800, block_char_cap=2400):
    """Капы в СИМВОЛАХ: счётчик токенов словесный, а llama использует BPE,
    для русского текста 1 BPE-токен ≈ 2.2 символа (словесный счёт занижает
    в ~2.4 раза). Слот 4096 токенов ≈ 9000 символов минус система/ответ."""
    blocks = []
    used_chars = 0
    for index, document in enumerate(documents, 1):
        meta = document.meta
        content = document.content
        if len(content) > block_char_cap:
            content = content[:block_char_cap] + " …"
        if blocks and used_chars + len(content) > char_cap:
            continue
        used_chars += len(content)
        blocks.append({
            "id": f"block_{index}",
            "document": meta.get("document_id") or meta.get("name"),
            "clause": meta.get("clause_number") or meta.get("locator") or "",
            "page": meta.get("page"),
            "text": content,
        })
    return blocks


def plan_answer(question, blocks, endpoint, timeout=180):
    listing = "\n\n".join(f"[{block['id']}] {block['document']} {block['clause']}\n{block['text']}" for block in blocks)
    payload = {
        "messages": [
            {"role": "system", "content": PLAN_PROMPT},
            {"role": "user", "content": f"QUESTION: {question}\n\nEVIDENCE BLOCKS:\n{listing}"},
        ],
        "temperature": 0,
        "max_tokens": 800,
        "response_format": {"type": "json_object", "schema": PLAN_SCHEMA},
    }
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.load(response)["choices"][0]["message"]["content"]
    return json.loads(raw), raw


def _action_supported(step, block):
    block_tokens = _tokens(block["text"])
    action_tokens = _tokens(step["action"])
    if not action_tokens:
        return False
    if not _digits(step["action"]) <= _digits(block["text"]):
        return False
    return len(action_tokens & block_tokens) / len(action_tokens) >= 0.4


def _field_supported(value, block):
    block_tokens = _tokens(block["text"])
    if not _digits(value) <= _digits(block["text"]):
        return False
    value_tokens = _tokens(value)
    return not value_tokens or len(value_tokens & block_tokens) / len(value_tokens) >= 0.5


def verify_plan(plan, blocks):
    by_id = {block["id"]: block for block in blocks}
    supported_steps = []
    missing = list(plan.get("missing_information") or [])
    for step in plan.get("steps") or []:
        block = by_id.get(step.get("evidence_id"))
        if block is None:
            missing.append(f"нет источника: {step.get('action', '')[:80]}")
            continue
        if not _action_supported(step, block):
            missing.append(f"не подтверждено источником: {step.get('action', '')[:80]}")
            continue
        clean = {"action": step["action"], "quote": block["text"], "block_id": block["id"], "document": block["document"], "clause": block["clause"]}
        for field in ("actor", "condition", "deadline"):
            value = step.get(field)
            clean[field] = value if value and _field_supported(value, block) else None
        supported_steps.append(clean)
    return supported_steps, missing


def verified_answer(question, documents, endpoint):
    """Возвращает dict в формате answer(): status/answer/steps/conflicts + план."""
    if not question.strip() or not documents:
        return {"status": "insufficient", "answer": [], "steps": [], "conflicts": [], "plan": None, "missing": []}
    blocks = build_evidence_blocks(documents)
    try:
        plan, raw = plan_answer(question, blocks, endpoint)
    except Exception as error:
        return {"status": "error", "answer": [], "steps": [], "conflicts": [], "error": str(error), "plan": None, "missing": []}
    supported, missing = verify_plan(plan, blocks)
    if not supported:
        return {"status": "insufficient", "answer": [], "steps": [], "conflicts": [], "plan": plan, "raw": raw, "missing": missing}
    steps = [{"source": step["block_id"], "quote": step["quote"], "action": step["action"], "actor": step.get("actor"), "condition": step.get("condition"), "deadline": step.get("deadline"), "document": step.get("document"), "clause": step.get("clause")} for step in supported]
    answer = steps[:3]
    return {"status": "supported_quotes", "answer": answer, "steps": steps, "conflicts": [], "plan": plan, "raw": raw, "missing": missing}
