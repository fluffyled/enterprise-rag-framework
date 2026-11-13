"""Thin demo and existing-Qwen adapters. No algorithm changes."""
import copy
import json
import os
import time
import urllib.request
from functools import lru_cache
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


def health():
    index = ROOT / "data" / "index.json"
    endpoint = os.environ.get("ANSWER_LLM_ENDPOINT", "http://127.0.0.1:8081/v1/chat/completions")
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


@lru_cache(maxsize=1)
def search_service(index_stamp, external_stamp):
    from answering.bridge import BaselineSearch
    return BaselineSearch()


def connected(request):
    from answering.core import generate
    index = ROOT / "data" / "index.json"
    external = ROOT / "data" / "external_sources.json"
    if not index.exists():
        return failure("Retrieval: индекс не найден. Подключите готовый индекс команды.")
    if not health()["llm"]:
        return failure("LLM недоступна. Запустите локальный сервер Qwen и проверьте ANSWER_LLM_ENDPOINT.")
    try:
        fragments = search_service(index.stat().st_mtime_ns, external.stat().st_mtime_ns if external.exists() else 0).search(request["question"])
    except Exception:
        return failure("Retrieval не удалось загрузить или выполнить поиск. Проверьте индекс и локальные зависимости.")
    result = generate(request["question"], fragments)
    if result["status"] == "error":
        return failure("LLM: ошибка генерации или проверки формата. Проверьте локальный сервер.")
    sources, numbers = [], {}
    def render(item):
        key = item["fragment_id"]
        if key not in numbers:
            numbers[key] = len(sources) + 1
            fragment = next(f for f in fragments if f.id == key)
            sources.append({"id": key, "document_id": item["document_id"],
                "document_title": item["title"], "locator": item["locator"],
                "excerpt": fragment.text, "url": item.get("url"), "date": fragment.date_hint})
        return f"{item['quote']} [{numbers[key]}]"
    answer = "\n\n".join(render(item) for item in result["answer"])
    steps = [render(item) for item in result["steps"]]
    conflicts = [render(c["left"]) + " / " + render(c["right"]) for c in result["conflicts"]]
    return {"status": result["status"], "answer": answer, "steps": steps, "sources": sources,
            "conflicts": conflicts, "missing_information": [],
            "warnings": result.get("warnings", []), "metadata": {"generator": "Qwen3.5-4B, исходный выбор цитат"}}


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
