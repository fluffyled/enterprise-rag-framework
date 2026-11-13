"""LLM-as-a-judge для ответов rag100 (локальная Qwen, temperature=0).

Для каждого отвечаемого вопроса оценивает:
- correctness: 0 (неверно), 1 (частично), 2 (верно) — семантическое сравнение
  ответа модели с reference_answer, а не буквальное совпадение;
- grounded: подтверждается ли ответ приведённой цитатой из контекста (yes/no).

Judge не заменяет ручную проверку: выборка проверяется вручную (см. отчёт этапа 5).
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

GOLD = ROOT / "data/rag100/rag_gold_qa.jsonl"
E2E = ROOT / "reports/retrieval_v3/end_to_end/rag100"

SCHEMA = {"type": "object", "properties": {"correctness": {"type": "integer", "enum": [0, 1, 2]}, "grounded": {"type": "string", "enum": ["yes", "no"]}, "comment": {"type": "string"}}, "required": ["correctness", "grounded"], "additionalProperties": False}

PROMPT = """Ты — строгий эксперт-оценщик. Сравни ОТВЕТ МОДЕЛИ с ЭТАЛОНОМ по смыслу (перефразирование допустимо).
Оцени correctness: 2 — ответ по существу верен, 1 — частично верен (есть верные элементы, но неполно или с неточностью), 0 — неверно.
Оцени grounded: yes, если ключевое утверждение ответа подтверждается ЦИТАТОЙ из документа, иначе no.
Ответь строго JSON: {{"correctness": 0|1|2, "grounded": "yes"|"no", "comment": "кратко"}}.

ВОПРОС: {question}
ЭТАЛОН: {reference}
ЦИТАТА ИЗ ДОКУМЕНТА: {quote}
ОТВЕТ МОДЕЛИ: {answer}
ЦИТАТЫ МОДЕЛИ: {citations}"""


def call_llm(prompt, endpoint, timeout=120):
    payload = {"messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": 150, "response_format": {"type": "json_object", "schema": SCHEMA}}
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content = json.load(response)["choices"][0]["message"]["content"]
    return json.loads(content)


def judge_experiment(experiment, endpoint):
    gold = {g["id"]: g for g in (json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip())}
    rows = json.loads((E2E / experiment / "per_query_results.json").read_text(encoding="utf-8"))
    results = []
    for row in rows:
        g = gold[row["id"]]
        if not g["answerable"]:
            continue
        result = row["result"]
        quotes = [item.get("quote", "") for item in (result.get("answer") or []) + (result.get("steps") or [])]
        answer = " ".join(quote for quote in quotes if quote)
        citations = "; ".join(item.get("quote", "") for item in (result.get("answer") or []))
        if result["status"] != "supported_quotes" or not answer:
            results.append({"id": row["id"], "correctness": None, "grounded": None, "comment": f"abstained:{result['status']}"})
            continue
        prompt = PROMPT.format(question=g["question"], reference=g["reference_answer"], quote=(g["evidence_quote"] or "")[:1500], answer=answer[:1500], citations=citations[:800])
        try:
            verdict = call_llm(prompt, endpoint)
        except Exception as error:
            verdict = {"correctness": None, "grounded": None, "comment": f"judge_error:{error}"}
        results.append({"id": row["id"], **verdict})
        time.sleep(0.05)
    scored = [r for r in results if r["correctness"] is not None]
    summary = {
        "experiment": experiment,
        "scored": len(scored),
        "correctness_mean": sum(r["correctness"] for r in scored) / len(scored) if scored else None,
        "fully_correct": sum(r["correctness"] == 2 for r in scored),
        "partial": sum(r["correctness"] == 1 for r in scored),
        "wrong": sum(r["correctness"] == 0 for r in scored),
        "grounded_yes": sum(r["grounded"] == "yes" for r in scored),
        "abstained_on_answerable": sum(r["correctness"] is None for r in results),
        "judge_errors": sum("judge_error" in (r.get("comment") or "") for r in results),
    }
    output = E2E / experiment / "judge.json"
    output.write_text(json.dumps({"summary": summary, "rows": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiments", required=True, help="comma-separated имена каталогов")
    parser.add_argument("--endpoint", default=os.environ.get("LLM_ENDPOINT", "http://127.0.0.1:8080/v1/chat/completions"))
    args = parser.parse_args()
    for experiment in args.experiments.split(","):
        print(json.dumps(judge_experiment(experiment, args.endpoint), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
