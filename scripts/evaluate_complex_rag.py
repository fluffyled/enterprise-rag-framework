"""Универсальный evaluator сложных вопросов (complex50, этап 2 ТЗ).

Работает с любой конфигурацией RAG и с oracle-контекстом.

Retrieval-метрики (по стадиям: rrf-кандидаты → reranked → selected/LLM context):
- document_recall — доля gold-документов в выдаче;
- unit_recall — доля gold source-units (страница/абзац);
- clause_recall — доля gold-clauses, покрытых текстом чанков (needle ⊆ chunk);
- evidence_recall — доля gold evidence, покрытых текстом;
- fact_coverage — доля required_facts, у которых покрыты ВСЕ evidence_ids;
- all_evidence_found — доля вопросов со всеми покрытыми evidence.

Метрики генерации (детерминированные прокси, не judge):
- step_recall — доля required_facts, покрытых цитатами ответа (пересечение
  цитат с evidence_quote факта);
- complete_at_all — доля ответов со всеми фактами;
- false_abstention — отказ при покрытых evidence в контексте;
- unsupported_quote_rate — доля цитат ответа без пересечения с gold evidence.

Oracle: --oracle передаёт LLM эталонные evidence вместо retrieval (только evaluation).
"""

import argparse
import json
import re
import sys
import time
import urllib.request
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


def load_gold():
    return [json.loads(line) for line in GOLD.read_text(encoding="utf-8").splitlines() if line.strip()]


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
    needles_by_doc = {}
    for row in gold:
        for evidence in row["gold_evidence"]:
            code_by_filename[evidence["document_filename"]] = evidence["document_code"]
            needles_by_doc.setdefault(evidence["document_code"], []).append((evidence["evidence_id"], norm(evidence["evidence_needle"])))

    chunk_units = {}
    chunk_clauses = {}
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
        content_norm = norm(chunk["content"])
        clauses = [eid for eid, needle in needles_by_doc.get(code, []) if needle and needle in content_norm]
        if clauses:
            chunk_clauses[meta["chunk_id"]] = clauses
    chunk_texts = {chunk["meta"]["chunk_id"]: chunk["content"] for chunk in chunks}
    return chunk_units, chunk_clauses, chunk_texts


def build_evidence_lookup(gold):
    """(code, normalized needle/quote) → (evidence_id, unit_id) для loose-покрытия."""
    lookup = {}
    for row in gold:
        for evidence in row["gold_evidence"]:
            tokens = frozenset(re.findall(r"\w+", norm(evidence["evidence_quote"]).lower()))
            lookup[(evidence["document_code"], evidence["evidence_id"])] = {
                "unit_id": evidence["source_unit_id"],
                "quote_tokens": tokens,
                "filename": evidence["document_filename"],
            }
    return lookup


def stage_coverage(documents, gold_row, chunk_units, chunk_clauses, evidence_lookup, chunk_texts):
    gold_docs = {e["document_filename"] for e in gold_row["gold_evidence"]}
    gold_units = {e["source_unit_id"] for e in gold_row["gold_evidence"]}
    gold_clauses = {e["evidence_id"] for e in gold_row["gold_evidence"]}
    covered_units = set()
    covered_clauses = set()
    for chunk_id in documents:
        covered_units.update(chunk_units.get(chunk_id, []))
        covered_clauses.update(chunk_clauses.get(chunk_id, []))
    # loose-покрытие: чанк пересекается с evidence_quote по токенам ≥ 0.5
    for chunk_id in documents:
        text_tokens = set(re.findall(r"\w+", norm(chunk_texts.get(chunk_id, "")).lower()))
        if not text_tokens:
            continue
        for (code, evidence_id), info in evidence_lookup.items():
            if evidence_id in covered_clauses:
                continue
            quote_tokens = info["quote_tokens"]
            if quote_tokens and len(text_tokens & quote_tokens) / len(quote_tokens) >= 0.5:
                covered_clauses.add(evidence_id)
                covered_units.add(info["unit_id"])
    for chunk_id in documents:
        for evidence in gold_row["gold_evidence"]:
            if evidence["evidence_id"] in chunk_clauses.get(chunk_id, []):
                covered_units.add(evidence["source_unit_id"])
    doc_hit = {info["filename"] for info in evidence_lookup.values() if info["unit_id"] in covered_units}
    fact_covered = sum(
        1 for fact in gold_row["required_facts"]
        if all(eid in covered_clauses for eid in fact["evidence_ids"])
    )
    return {
        "document_recall": len(doc_hit & gold_docs) / len(gold_docs) if gold_docs else 0.0,
        "unit_recall": len(covered_units & gold_units) / len(gold_units) if gold_units else 0.0,
        "clause_recall": len(covered_clauses & gold_clauses) / len(gold_clauses) if gold_clauses else 0.0,
        "evidence_recall": len(covered_clauses & gold_clauses) / len(gold_clauses) if gold_clauses else 0.0,
        "fact_coverage": fact_covered / len(gold_row["required_facts"]) if gold_row["required_facts"] else 0.0,
        "all_evidence_found": float(covered_clauses >= gold_clauses),
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


def generation_metrics(result, gold_row):
    quotes = [item.get("quote", "") for item in (result.get("answer") or []) + (result.get("steps") or [])]
    status = result.get("status")
    facts_covered = 0
    for fact in gold_row["required_facts"]:
        if any(quote_covers_fact(quote, gold_row, fact) for quote in quotes):
            facts_covered += 1
    total_facts = len(gold_row["required_facts"])
    unsupported = 0
    for quote in quotes:
        if not any(quote_covers_fact(quote, gold_row, fact) for fact in gold_row["required_facts"]):
            unsupported += 1
    return {
        "step_recall": facts_covered / total_facts if total_facts else 0.0,
        "complete_at_all": float(facts_covered == total_facts),
        "false_abstention": float(status == "insufficient"),
        "unsupported_quote_rate": unsupported / len(quotes) if quotes else 0.0,
        "status": status,
        "quote_count": len(quotes),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/retrieval_bge_adaptive_rerank.yaml")
    parser.add_argument("--index-path", default=None)
    parser.add_argument("--split", default="all")
    parser.add_argument("--name", required=True)
    parser.add_argument("--llm", action="store_true")
    parser.add_argument("--oracle", action="store_true")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    args = parser.parse_args()

    gold_rows = [row for row in load_gold() if args.split == "all" or row["split"] == args.split]
    index_path = args.index_path or str(ROOT / "data/index.json")
    chunk_units, chunk_clauses, chunk_texts = build_indexes(load_gold(), index_path)
    evidence_lookup = build_evidence_lookup(load_gold())
    if args.oracle:
        for row in load_gold():
            for evidence in row["gold_evidence"]:
                chunk_units[evidence["evidence_id"]] = [evidence["source_unit_id"]]
                chunk_clauses[evidence["evidence_id"]] = [evidence["evidence_id"]]
                chunk_texts[evidence["evidence_id"]] = evidence["evidence_quote"]

    config = None if args.oracle else load_config(ROOT / args.config)
    retriever = None if args.oracle else Retriever(config=config, index_path=args.index_path)

    rows = []
    for gold_row in gold_rows:
        started = time.perf_counter()
        trace = None
        retrieval_seconds = 0.0
        if args.oracle:
            documents = [Document(content=e["evidence_quote"], meta={"document_id": e["document_filename"], "name": e["document_filename"], "chunk_id": e["evidence_id"]}) for e in gold_row["gold_evidence"]]
            stage_chunks = {"oracle": [d.meta["chunk_id"] for d in documents]}
        else:
            retrieval_started = time.perf_counter()
            search = retriever.search(gold_row["question"], config=config)
            retrieval_seconds = time.perf_counter() - retrieval_started
            trace = search.to_dict()
            documents = list(search)
            stage_chunks = {
                "rrf": [item["meta"].get("chunk_id") for item in trace["stages"].get("rrf", [])],
                "reranked": [item["meta"].get("chunk_id") for item in trace["stages"].get("cross_encoder", [])],
                "selected": [item["meta"].get("chunk_id") for item in trace["results"]],
            }
        stages = {}
        for stage_name, chunk_ids in stage_chunks.items():
            stages[stage_name] = stage_coverage(chunk_ids, gold_row, chunk_units, chunk_clauses, evidence_lookup, chunk_texts)
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
            generation_started = time.perf_counter()
            result = call_llm(gold_row["question"], documents, args.endpoint)
            row["generation_seconds"] = time.perf_counter() - generation_started
            row["result"] = {key: value for key, value in result.items() if key != "raw"}
            row["raw_llm_answer"] = result.get("raw")
            row["generation"] = generation_metrics(result, gold_row)
            row["prompt_sha256"] = __import__("hashlib").sha256(PROMPT.encode()).hexdigest()
            row["context_tokens"] = sum(len(re.findall(r"\w+|[^\w\s]", document.content)) for document in documents)
        rows.append(row)
        print(args.name, gold_row["id"], f"{time.perf_counter() - started:.2f}s", flush=True)

    output = OUT_ROOT / args.name
    output.mkdir(parents=True, exist_ok=True)
    (output / "per_query_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = {"questions": len(rows), "oracle": args.oracle}
    for stage_name in ("rrf", "reranked", "selected", "oracle"):
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
            for key in ("step_recall", "complete_at_all", "false_abstention", "unsupported_quote_rate")
        }
        metrics["latency"] = {
            "retrieval_median": sorted(row["retrieval_seconds"] for row in rows)[len(rows) // 2],
            "generation_median": sorted(row.get("generation_seconds", 0.0) for row in rows)[len(rows) // 2],
            "context_tokens_mean": sum(row.get("context_tokens", 0) for row in rows) / len(rows),
        }
    (output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
