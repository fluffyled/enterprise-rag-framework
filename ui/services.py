"""Thin demo and existing-Qwen adapters. No algorithm changes."""
import copy
import json
import os
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {"answered", "partial", "insufficient", "conflict", "error"}


def fixtures():
    return json.loads((ROOT / "demo_fixtures" / "answers.json").read_text(encoding="utf-8-sig"))


def failure(message):
    return {"status": "error", "answer": "", "steps": [], "sources": [],
            "conflicts": [], "missing_information": [], "error": message, "metadata": {}}


def validate_response(result):
    if not isinstance(result, dict) or result.get("status") not in STATUSES:
        raise ValueError("Backend вернул неизвестный статус")
    if not isinstance(result.get("answer"), str):
        raise ValueError("Backend вернул некорректный текст ответа")
    for field in ("steps", "sources", "conflicts", "missing_information"):
        if not isinstance(result.get(field), list):
            raise ValueError(f"Backend: {field} должен быть списком")
    ids = set()
    for source in result["sources"]:
        if not isinstance(source, dict) or any(not isinstance(source.get(k), str) for k in ("id", "document_title", "excerpt")):
            raise ValueError("Backend вернул некорректный источник")
        if not source["id"] or source["id"] in ids:
            raise ValueError("Backend вернул повторяющийся ID")
        ids.add(source["id"])
    if any(not isinstance(x, str) for x in result["steps"] + result["conflicts"] + result["missing_information"]):
        raise ValueError("Backend вернул некорректный список сообщений")
    return result


def health(snapshot=None, generation="legacy"):
    from navigator.rag_service import index_path
    index = index_path(snapshot)
    endpoint = (os.environ.get("ANSWER_LLM_ENDPOINT", "http://127.0.0.1:8081/v1/chat/completions")
                if generation == "g2" else os.environ.get("LLM_ENDPOINT", "http://127.0.0.1:8080/v1/chat/completions"))
    from answering.core import check_endpoint
    try:
        check_endpoint(endpoint)
        u = urlsplit(endpoint)
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(f"{u.scheme}://{u.netloc}/health", timeout=2) as response:
            llm = response.status == 200
    except Exception:
        llm = False
    return {"index": index.exists(), "llm": llm}


def connected(request):
    from navigator.rag_service import ask

    response = ask(request["question"], request.get("retrieval"), request.get("generation"),
                   snapshot=request.get("snapshot"), diagnostics=request.get("diagnostics", False))
    numbers = {source["id"]: i for i, source in enumerate(response.sources, 1)}
    def render(item):
        return item["text"] + "".join(f" [источник {numbers[key]}]" for key in item["citations"])

    fields = {"actor": "Ответственный", "recipient": "Адресат", "deadline": "Срок",
              "condition": "Условие", "exception": "Исключение", "alternative": "Вариант"}
    modalities = {"permitted": "Допустимо", "prohibited": "Запрещено", "alternative": "Вариант",
                  "conditional": "При выполнении условия", "exception": "Исключение"}
    steps = []
    for item in response.steps:
        details = [f"{label} — {item[key]}" for key, label in fields.items() if item.get(key)]
        if item.get("depends_on"):
            details.append("После " + ", ".join(item["depends_on"]))
        prefix = modalities.get(item.get("modality"))
        steps.append(" · ".join(filter(None, [prefix, render(item), *details])))
    return {"status": response.status, "answer": "\n\n".join(map(render, response.summary)),
            "steps": steps, "sources": response.sources, "conflicts": list(map(render, response.conflicts)),
            "missing_information": response.missing_requirements, "warnings": response.warnings,
            "metadata": response.diagnostics, "error": response.error}


def ask_question(request, mode):
    started = time.perf_counter()
    try:
        question = request.get("question", "").strip()
        if not question or len(question) > 6000:
            raise ValueError("Введите вопрос длиной от 1 до 6000 символов.")
        if mode == "Демонстрационный":
            item = next((x for x in fixtures() if x["question"] == question), None)
            result = copy.deepcopy(item["response"]) if item else failure("В деморежиме выберите один из тестовых вопросов. Произвольные вопросы доступны при подключении backend.")
        else:
            result = connected(request)
        validate_response(result)
    except Exception as exc:
        result = failure(str(exc) if isinstance(exc, ValueError) else "Ошибка адаптера. Проверьте подключение backend.")
    result.setdefault("metadata", {})["latency_ms"] = round((time.perf_counter() - started) * 1000)
    result["metadata"]["mode"] = mode
    return result
