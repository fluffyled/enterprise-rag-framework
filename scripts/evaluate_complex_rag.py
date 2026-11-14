"""Универсальный evaluator сложных вопросов (complex50, этап 2 ТЗ; аудит v4.1).

Семантика метрик (зафиксирована, этап 4 аудита):
- document_recall — доля gold-документов, представленных в выдаче (по юнитам).
- unit_recall — доля gold source-units (страница/абзац) в выдаче.
- clause_recall (главная) — объединение strict+soft; strict = дословное
  вхождение needle В ДОКУМЕНТЕ gold evidence (это проверка текстового
  evidence в правильном документе, НЕ проверка точного clause ID);
  soft = токенное пересечение с evidence_quote ≥ 0.5 (диагностическая).
- fact_coverage — доля required_facts, у которых покрыты ВСЕ evidence.
- all_evidence_found — доля вопросов с полным покрытием.
- legacy_* — прежние определения (без учёта документа / по полным цитатам),
  сохранены ТОЛЬКО для сравнения с историческими исследованиями.

Gold используется только здесь, в offline evaluation; runtime-поиск его
не видит. Ответы LLM оцениваются агентом генерации; здесь generation-метрики
приведены для совместимости прогонов.
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from haystack import Document

from navigator.answer import PROMPT, selected_quotes, sentence_options
from navigator.config import load_config
from navigator.retrieval import Retriever

GOLD = ROOT / "data/hrag50/hierarchical_complex_qa_50.jsonl"
OUT_ROOT = ROOT / "reports/retrieval_experiments/complex50"

ABZ_RE = re.compile(r"^\u0430\u0431\u0437\u0430\u0446 (\d+)")


def norm(text):
    return re.sub(r"\s+", " ", text or " ").strip()


def load_gold(path=None):
    source = Path(path) if path else GOLD
    return [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_indexes(gold, index_path):
    """Маппинг чанков индекса: units (doc/page|paragraph) и clause-покрытие по тексту.

    PDF: юнит напрямую из meta.page. DOCX: нумерация абзацев у датасета своя,
    поэтому покрытие определяется текстом: точное вхождение needle (strict) или
    пересечение токенов с evidence_quote ≥ 0.5 (loose). Юнит DOCX приписывается
    через покрытое evidence.
    """
    index = json.loads(Path(index_path).read_text(encoding="utf-8"))
    chunks = index["documents"]
    code_by_filename = {}
    for row in gold:
        for evidence in row["gold_evidence"]:
            code_by_filename[evidence["document_filename"]] = evidence["document_code"]

    chunk_units = {}
    for chunk in chunks:
        meta = chunk["meta"]
        code = code_by_filename.get(meta["name"])
        if not code:
            continue
        units = []
        if meta["name"].lower().endswith(".pdf"):
            page = meta.get("page")
            if page and str(page).isdigit():
                units.append(f"{code}::pdf_page::{int(page)}")
        chunk_units[meta["chunk_id"]] = units
    return chunk_units


def stage_coverage(items, gold_row, chunk_units):
    """Покрытие gold стадией. items — список (chunk_id, content, document).

    Аудит D2: needle/soft совпадения засчитываются ТОЛЬКО в контенте того же
    документа, что и gold evidence (в корпусе есть дубликаты положений D05/D14 —
    совпадение в чужом документе не является нахождением доказательства).
    Аудит D3: strict (дословный needle) и soft (токенное пересечение с цитатой
    ≥ 0.5) разделены; итог — объединение. Аудит: legacy-ключи — прежнее
    поведение без проверки документа, для сравнения до/после.
    """
    gold_docs = {e["document_filename"] for e in gold_row["gold_evidence"]}
    gold_units = {e["source_unit_id"] for e in gold_row["gold_evidence"]}
    gold_clauses = {e["evidence_id"] for e in gold_row["gold_evidence"]}
    strict, soft, legacy = set(), set(), set()
    covered_units = set()
    filename_by_code = {e["document_code"]: e["document_filename"] for e in gold_row["gold_evidence"]}
    for chunk_id, content, item_document in items:
        covered_units.update(chunk_units.get(chunk_id, []))
        content_norm = norm(content)
        content_tokens = set(re.findall(r"\w+", content_norm.lower()))
        for evidence in gold_row["gold_evidence"]:
            evidence_id = evidence["evidence_id"]
            needle = norm(evidence["evidence_needle"])
            quote_tokens = set(re.findall(r"\w+", norm(evidence["evidence_quote"]).lower()))
            is_strict = bool(needle) and needle in content_norm
            is_soft = bool(quote_tokens) and len(content_tokens & quote_tokens) / len(quote_tokens) >= 0.5
            if is_strict or is_soft:
                legacy.add(evidence_id)
            if evidence["document_filename"] != item_document:
                continue  # D2: совпадение в другом документе не считается
            if is_strict:
                strict.add(evidence_id)
                covered_units.add(evidence["source_unit_id"])
            elif is_soft:
                soft.add(evidence_id)
                covered_units.add(evidence["source_unit_id"])
    covered = strict | soft
    doc_hit = {filename_by_code.get(unit.split("::")[0]) for unit in covered_units}
    total_facts = len(gold_row["required_facts"])
    fact_covered = sum(1 for fact in gold_row["required_facts"] if all(eid in covered for eid in fact["evidence_ids"]))
    fact_covered_strict = sum(1 for fact in gold_row["required_facts"] if all(eid in strict for eid in fact["evidence_ids"]))
    fact_covered_legacy = sum(1 for fact in gold_row["required_facts"] if all(eid in legacy for eid in fact["evidence_ids"]))
    return {
        "document_recall": len(doc_hit & gold_docs) / len(gold_docs) if gold_docs else 0.0,
        "unit_recall": len(covered_units & gold_units) / len(gold_units) if gold_units else 0.0,
        "clause_recall": len(covered & gold_clauses) / len(gold_clauses) if gold_clauses else 0.0,
        "clause_recall_strict": len(strict & gold_clauses) / len(gold_clauses) if gold_clauses else 0.0,
        "clause_recall_soft_only": len((soft - strict) & gold_clauses) / len(gold_clauses) if gold_clauses else 0.0,
        "evidence_recall": len(covered & gold_clauses) / len(gold_clauses) if gold_clauses else 0.0,
        "fact_coverage": fact_covered / total_facts if total_facts else 0.0,
        "fact_coverage_strict": fact_covered_strict / total_facts if total_facts else 0.0,
        "all_evidence_found": float(covered >= gold_clauses),
        "clause_recall_legacy": len(legacy & gold_clauses) / len(gold_clauses) if gold_clauses else 0.0,
        "fact_coverage_legacy": fact_covered_legacy / total_facts if total_facts else 0.0,
    }


def call_llm(question, docs, endpoint, timeout=180):
    """Тот же вызов, что navigator.answer.answer, но с сохранением сырого ответа."""
    context = sentence_options(docs)
    valid_ids = [o["id"] for o in context]
    if not question.strip() or not docs or not valid_ids:
        return {"status": "insufficient", "answer": [], "steps": [], "conflicts": [], "raw": None, "context_sentences": 0}
    id_schema = {"type": "integer", "enum": valid_ids}
    schema = {"type": "object", "properties": {
        "answer_ids": {"type": "array", "items": id_schema, "maxItems": 3},
        "step_ids": {"type": "array", "items": id_schema, "maxItems": 5},
        "conflict_pairs": {"type": "array", "items": {"type": "array", "items": id_schema, "minItems": 2, "maxItems": 2}, "maxItems": 2},
        "insufficient": {"type": "boolean"}}, "required": ["answer_ids", "step_ids", "conflict_pairs", "insufficient"], "additionalProperties": False}
    formatted = "QUESTION: " + question + "\nSOURCE SENTENCES:\n" + "\n".join(f"[{o['id']}] {o['text']}" for o in context) + "\nQUESTION: " + question
    payload = {"messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": formatted}], "temperature": 0, "max_tokens": 300, "response_format": {"type": "json_object", "schema": schema}}
    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = json.load(response)["choices"][0]["message"]["content"]
        parsed = json.loads(text)
        result = selected_quotes(parsed, context, docs)
        result["raw"] = text
        result["context_sentences"] = len(context)
        return result
    except Exception as error:
        return {"status": "error", "answer": [], "steps": [], "conflicts": [], "error": str(error), "raw": None, "context_sentences": len(context)}


def quote_covers_fact(quote, gold_row, fact):
    quote_norm = norm(quote).lower()
    for evidence in gold_row["gold_evidence"]:
        if evidence["evidence_id"] not in fact["evidence_ids"]:
            continue
        evidence_norm = norm(evidence["evidence_quote"]).lower()
        if evidence_norm and (evidence_norm in quote_norm or quote_norm in evidence_norm):
            return True
        quote_tokens = set(re.findall(r"\w+", quote_norm))
        evidence_tokens = set(re.findall(r"\w+", evidence_norm))
        if evidence_tokens and len(quote_tokens & evidence_tokens) / len(evidence_tokens) >= 0.6:
            return True
    return False


def step_text_covers_fact(step_text, gold_row, fact):
    """Аудит D4: проверка СОДЕРЖИМОГО шага (а не цитатного блока) против
    объединённого содержимого ВСЕХ обязательных evidence факта: цифры шага ⊆
    цифрам evidence-объединения и ≥ 50% содержательных слов шага (длины ≥ 4)
    присутствуют в нём. Составной факт покрыт только целиком."""
    text_norm = norm(step_text).lower()
    if not text_norm:
        return False
    text_tokens = {t for t in re.findall(r"\w+", text_norm) if len(t) >= 4}
    text_digits = set(re.findall(r"\d+", text_norm))
    evidence_tokens, evidence_digits = set(), set()
    for evidence in gold_row["gold_evidence"]:
        if evidence["evidence_id"] not in fact["evidence_ids"]:
            continue
        evidence_norm = norm(evidence["evidence_quote"]).lower()
        evidence_tokens |= set(re.findall(r"\w+", evidence_norm))
        evidence_digits |= set(re.findall(r"\d+", evidence_norm))
    if text_digits and not text_digits <= evidence_digits:
        return False
    if text_tokens and len(text_tokens & evidence_tokens) / len(text_tokens) < 0.5:
        return False
    return True


def generation_metrics(result, gold_row):
    """Аудит D4/D5: verified-режим оценивает текст шагов (action+поля),
    quotes-режим — цитаты; error и false_abstention разделены;
    legacy_step_recall — прежняя оценка по полным цитатным блокам (завышение)."""
    status = result.get("status")
    is_verified = bool(result.get("steps")) and all("action" in item for item in result["steps"])
    total_facts = len(gold_row["required_facts"])
    legacy_quotes = [item.get("quote", "") for item in (result.get("answer") or []) + (result.get("steps") or [])]
    if is_verified and status == "supported_quotes":
        steps_text = [" ".join(filter(None, (item.get("action", ""), item.get("actor") or "", item.get("condition") or "", item.get("deadline") or ""))) for item in result["steps"]]
        facts_covered = sum(1 for fact in gold_row["required_facts"] if any(step_text_covers_fact(text, gold_row, fact) for text in steps_text))
        unsupported = sum(1 for text in steps_text if not any(step_text_covers_fact(text, gold_row, fact) for fact in gold_row["required_facts"]))
        unit_count = len(steps_text)
    else:
        facts_covered = sum(1 for fact in gold_row["required_facts"] if any(quote_covers_fact(quote, gold_row, fact) for quote in legacy_quotes))
        unsupported = sum(1 for quote in legacy_quotes if not any(quote_covers_fact(quote, gold_row, fact) for fact in gold_row["required_facts"]))
        unit_count = len(legacy_quotes)
    legacy_covered = sum(1 for fact in gold_row["required_facts"] if any(quote_covers_fact(quote, gold_row, fact) for quote in legacy_quotes))
    return {
        "step_recall": facts_covered / total_facts if total_facts else 0.0,
        "complete_at_all": float(facts_covered == total_facts and status == "supported_quotes"),
        "false_abstention": float(status == "insufficient"),
        "error_rate": float(status == "error"),
        "unsupported_quote_rate": unsupported / unit_count if unit_count else 0.0,
        "status": status,
        "quote_count": unit_count,
        "legacy_step_recall": legacy_covered / total_facts if total_facts else 0.0,
    }


_RETRIEVER_CACHE = {}


def get_retriever(config, index_path):
    """Кэш Retriever: модели (BGE/reranker) остаются в памяти между прогонами."""
    key = (str(config), str(index_path))
    if key not in _RETRIEVER_CACHE:
        _RETRIEVER_CACHE[key] = Retriever(config=load_config(ROOT / config), index_path=index_path)
    return _RETRIEVER_CACHE[key]


def main(argv=None):
    args = parse_args(argv)
    return run(args)


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/retrieval_bge_adaptive_rerank.yaml")
    parser.add_argument("--index-path", default=None)
    parser.add_argument("--split", default="all")
    parser.add_argument("--name", required=True)
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--generation-mode", choices=("quotes", "verified"), default="quotes")
    parser.add_argument("--parallel", type=int, default=4, help="параллельных LLM-вызовов (слоты llama-server)")
    parser.add_argument("--oracle", action="store_true")
    parser.add_argument("--gold-path", default=None, help="альтернативный gold (например grouped split)")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    return parser.parse_args(argv)


def run(args):
    gold_all = load_gold(args.gold_path)
    gold_rows = [row for row in gold_all if args.split == "all" or row["split"] == args.split]
    index_path = args.index_path or str(ROOT / "data/index.json")
    chunk_units = build_indexes(gold_all, index_path)

    config = None if args.oracle else load_config(ROOT / args.config)
    retriever = None if args.oracle else get_retriever(args.config, args.index_path)

    rows = []
    for gold_row in gold_rows:
        started = time.perf_counter()
        trace = None
        retrieval_seconds = 0.0
        if args.oracle:
            documents = [Document(content=e["evidence_quote"], meta={"document_id": e["document_filename"], "name": e["document_filename"], "chunk_id": e["evidence_id"]}) for e in gold_row["gold_evidence"]]
            stage_chunks = {"oracle": [(e["evidence_id"], e["evidence_quote"], e["document_filename"]) for e in gold_row["gold_evidence"]]}
        else:
            retrieval_started = time.perf_counter()
            search = retriever.search(gold_row["question"], config=config)
            retrieval_seconds = time.perf_counter() - retrieval_started
            trace = search.to_dict()
            documents = list(search)
            def snap(item):
                return (item["meta"].get("chunk_id"), item["content"], item.get("document_id"))
            stage_chunks = {
                "rrf": [snap(item) for item in trace["stages"].get("rrf", [])],
                "reranked": [snap(item) for item in trace["stages"].get("cross_encoder", [])],
                "selected": [snap(item) for item in trace["results"]],
            }
            if trace.get("metadata", {}).get("multi_hop"):
                # Аудит: в multi-hop прогонах стадии rrf/reranked относятся только
                # к базовому вопросу (поиски по подзадачам — в rounds диагностике).
                stage_chunks["base_rrf"] = stage_chunks.pop("rrf")
                stage_chunks["base_reranked"] = stage_chunks.pop("reranked")
        stages = {}
        for stage_name, items in stage_chunks.items():
            stages[stage_name] = stage_coverage(items, gold_row, chunk_units)
        row = {
            "id": gold_row["id"],
            "split": gold_row["split"],
            "question": gold_row["question"],
            "question_type": gold_row.get("question_type"),
            "retrieval_seconds": retrieval_seconds,
            "stages": stages,
            "trace": trace,
            "oracle": args.oracle,
        }
        if args.llm:
            row["_gold_row"] = gold_row
            row["_documents"] = documents
        rows.append(row)
        print(args.name, gold_row["id"], f"{time.perf_counter() - started:.2f}s", flush=True)

    if args.llm and rows:
        # генерация — параллельно через слоты llama-server (--parallel)
        def generate(row):
            gold_row = row["_gold_row"]
            documents = row["_documents"]
            generation_started = time.perf_counter()
            if args.generation_mode == "verified":
                from navigator.verified_answer import verified_answer
                result = verified_answer(gold_row["question"], documents, args.endpoint)
                raw = result.pop("raw", None)
                result["raw"] = raw
            else:
                result = call_llm(gold_row["question"], documents, args.endpoint)
            row["generation_seconds"] = time.perf_counter() - generation_started
            row["result"] = {key: value for key, value in result.items() if key not in ("raw", "plan")}
            row["plan"] = result.get("plan")
            row["raw_llm_answer"] = result.get("raw")
            row["generation"] = generation_metrics(result, gold_row)
            row["generation"]["missing_count"] = len(result.get("missing") or [])
            row["context_tokens"] = sum(len(re.findall(r"\w+|[^\w\s]", document.content)) for document in documents)
            del row["_gold_row"], row["_documents"]
            return row

        workers = max(1, args.parallel)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            rows = list(executor.map(generate, rows))
        import hashlib
        for row in rows:
            row["prompt_sha256"] = hashlib.sha256(PROMPT.encode()).hexdigest()

    output = OUT_ROOT / args.name
    output.mkdir(parents=True, exist_ok=True)
    (output / "per_query_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = {"questions": len(rows), "oracle": args.oracle}
    for stage_name in ("rrf", "reranked", "selected", "oracle", "base_rrf", "base_reranked"):
        stage_rows = [row["stages"][stage_name] for row in rows if stage_name in row["stages"]]
        if not stage_rows:
            continue
        metrics[stage_name] = {
            key: sum(row[key] for row in stage_rows) / len(stage_rows)
            for key in stage_rows[0]
        }
    if args.llm:
        gen_rows = [row["generation"] for row in rows]
        metrics["generation"] = {
            key: sum(row[key] for row in gen_rows) / len(gen_rows)
            for key in ("step_recall", "complete_at_all", "false_abstention", "error_rate", "unsupported_quote_rate", "legacy_step_recall")
        }
        metrics["latency"] = {
            "retrieval_median": sorted(row["retrieval_seconds"] for row in rows)[len(rows) // 2],
            "generation_median": sorted(row.get("generation_seconds", 0.0) for row in rows)[len(rows) // 2],
            "context_tokens_mean": sum(row.get("context_tokens", 0) for row in rows) / len(rows),
        }
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return metrics


if __name__ == "__main__":
    main()
