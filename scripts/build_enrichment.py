"""Offline LLM Enrichment: карточки фактов и синтетические вопросы по пунктам.

Запускается ОДИН РАЗ при индексации (offline): Qwen анализирует каждый clause
из clause store и возвращает факты (субъект/действие/объект/условие/срок +
точная цитата) и типовые вопросы сотрудников. Затем детерминированная
валидация: цитата обязана быть подстрокой пункта, цифры сроков — из цитаты.

Хранение: data/enrichment/fact_cards.jsonl, synthetic_questions.jsonl,
enrichment_manifest.json. Gold-разметка бенчмарков НЕ используется.
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CLAUSES = ROOT / "data/clauses/clauses.json"
OUT_DIR = ROOT / "data/enrichment"

ENRICHER_PROMPT = """Ты анализируешь внутренние нормативные документы. Получишь список пунктов (clause_ref — их номера по порядку). Для КАЖДОГО пункта извлеки факты, которые прямо подтверждаются его текстом, и сформулируй типовые вопросы сотрудников.

Правила:
1. Не добавляй внешние знания; только содержание пункта.
2. quote — дословная подстрока пункта (можно сокращать края, но не переписывать слова).
3. deadline пустая строка, если срок не установлен явно; иначе цифры срока должны быть из quote.
4. Не превращай разрешение в обязанность; не теряй отрицания и исключения.
5. Не объединяй независимые требования в один факт.
6. Вопросы — естественные формулировки сотрудников (официальные и разговорные), на которые текст пункта действительно даёт ответ. 2-4 вопроса на пункт.
7. Ответ строго JSON по схеме."""


def make_schema(batch_size):
    fact = {
        "type": "object",
        "properties": {
            "actor": {"type": "string"},
            "action": {"type": "string"},
            "object": {"type": "string"},
            "condition": {"type": "string"},
            "deadline": {"type": "string"},
            "quote": {"type": "string"},
        },
        "required": ["actor", "action", "quote"],
        "additionalProperties": False,
    }
    item = {
        "type": "object",
        "properties": {
            "clause_ref": {"type": "integer"},
            "facts": {"type": "array", "maxItems": 3, "items": fact},
            "questions": {"type": "array", "maxItems": 3, "items": {"type": "string"}},
        },
        "required": ["clause_ref", "facts", "questions"],
        "additionalProperties": False,
    }
    return {"type": "object", "properties": {"results": {"type": "array", "maxItems": batch_size, "items": item}}, "required": ["results"], "additionalProperties": False}


def norm(text):
    return re.sub(r"\s+", " ", text or " ").strip()


def digits(text):
    return set(re.findall(r"\d+", text or ""))


def call_llm(payload, endpoint, timeout=240):
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)["choices"][0]["message"]["content"]


def validate_fact(fact, clause_text):
    quote = norm(fact.get("quote"))
    clause_norm = norm(clause_text)
    if len(quote) < 10 or quote not in clause_norm:
        return None
    action = norm(fact.get("action"))
    if len(action) < 3:
        return None
    deadline = norm(fact.get("deadline"))
    if deadline:
        if not digits(deadline) <= digits(quote):
            return None
        q_tokens = {t[:5] for t in re.findall(r"\w+", quote.lower()) if len(t) >= 3}
        d_tokens = {t[:5] for t in re.findall(r"\w+", deadline.lower()) if len(t) >= 3}
        if d_tokens and len(d_tokens & q_tokens) / len(d_tokens) < 0.5:
            return None
    return {**fact, "quote": quote}


def validate_question(question, clause_text):
    question = norm(question)
    if len(question) < 15 or not question.endswith("?"):
        return None
    q_tokens = {t[:5] for t in re.findall(r"\w+", question.lower()) if len(t) >= 5}
    c_tokens = {t[:5] for t in re.findall(r"\w+", clause_text.lower()) if len(t) >= 5}
    if q_tokens and not (q_tokens & c_tokens):
        return None
    return question


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--max-clause-chars", type=int, default=2200)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--parallel", type=int, default=4)
    args = parser.parse_args()

    from navigator.parent_expansion import load_clause_store
    store = load_clause_store(CLAUSES)
    clauses = []
    for key, entry in store.items():
        for clause in entry["clauses"]:
            clauses.append({"sha": entry.get("sha256", key), "document": entry["document_id"], **clause})
    if args.limit:
        clauses = clauses[: args.limit]

    batches = [clauses[i:i + args.batch_size] for i in range(0, len(clauses), args.batch_size)]
    fact_cards = []
    questions = []
    failed_batches = 0
    started_all = time.perf_counter()
    state = {"lock": __import__("threading").Lock()}

    def process_batch(batch_index, batch):
        nonlocal failed_batches
        listing = "\n\n".join(
            f"clause_ref: {i}\n{clause['full_text'][:args.max_clause_chars]}"
            for i, clause in enumerate(batch)
        )
        payload = {
            "messages": [
                {"role": "system", "content": ENRICHER_PROMPT},
                {"role": "user", "content": listing},
            ],
            "temperature": 0,
            "max_tokens": 1800,
            "response_format": {"type": "json_object", "schema": make_schema(len(batch))},
        }
        try:
            content = call_llm(payload, args.endpoint)
        except Exception as error:
            with state["lock"]:
                failed_batches += 1
            print(f"batch {batch_index}: FAILED {error}", flush=True)
            return
        try:
            results = json.loads(content)["results"]
        except json.JSONDecodeError:
            repaired = content[:content.rfind("}") + 1].rstrip().rstrip(",") + "]}"
            try:
                results = json.loads(repaired)["results"]
            except Exception:
                with state["lock"]:
                    failed_batches += 1
                print(f"batch {batch_index}: FAILED truncated json", flush=True)
                return
        local_facts, local_questions = [], []
        for item in results:
            ref = item.get("clause_ref")
            if type(ref) is not int or not 0 <= ref < len(batch):
                continue
            clause = batch[ref]
            for fact in item.get("facts", []):
                clean = validate_fact(fact, clause["full_text"])
                if clean:
                    local_facts.append({
                        "fact_id": hashlib.sha256(f"{clause['clause_id']}:{clean['action'][:60]}".encode()).hexdigest()[:16],
                        "document": clause["document"],
                        "clause_id": clause["clause_id"],
                        "clause_number": clause["number"],
                        **{key: norm(clean.get(key, "")) for key in ("actor", "action", "object", "condition", "deadline", "quote")},
                    })
            for question in item.get("questions", []):
                clean_q = validate_question(question, clause["full_text"])
                if clean_q:
                    local_questions.append({
                        "question_id": hashlib.sha256(f"{clause['clause_id']}:{clean_q}".encode()).hexdigest()[:16],
                        "question": clean_q,
                        "document": clause["document"],
                        "clause_id": clause["clause_id"],
                        "clause_number": clause["number"],
                    })
        with state["lock"]:
            fact_cards.extend(local_facts)
            questions.extend(local_questions)
            if batch_index % 10 == 0:
                print(f"batch {batch_index}/{len(batches)} facts={len(fact_cards)} questions={len(questions)}", flush=True)

    with ThreadPoolExecutor(max_workers=args.parallel) as executor:
        list(executor.map(lambda args_: process_batch(*args_), enumerate(batches)))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "fact_cards.jsonl").write_text("\n".join(json.dumps(card, ensure_ascii=False) for card in fact_cards), encoding="utf-8")
    (OUT_DIR / "synthetic_questions.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in questions), encoding="utf-8")
    manifest = {
        "clauses_total": len(clauses),
        "batches": len(batches),
        "failed_batches": failed_batches,
        "fact_cards": len(fact_cards),
        "synthetic_questions": len(questions),
        "seconds": round(time.perf_counter() - started_all, 1),
        "prompt_sha256": hashlib.sha256(ENRICHER_PROMPT.encode()).hexdigest(),
        "model": "Qwen2.5-3B-Instruct q4_k_m (llama.cpp CUDA)",
    }
    (OUT_DIR / "enrichment_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
