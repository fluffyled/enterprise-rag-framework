"""Multi-Hop Retrieval: декомпозиция вопроса + поиск по подзадачам (H3/H4).

Пайплайн (этап 6 ТЗ):
1. План поиска: LLM-декомпозиция (constrained JSON, fallback на правила).
   Подвопросы — поисковые гипотезы, не факты.
2. Отдельный retrieval по каждому подвопросу (BGE-M3 + BM25 + reranker),
   объединение с сохранением информации, какой подвопрос нашёл доказательство.
3. Иерархическое расширение (parent + related) для объединённых кандидатов.
4. Проверка покрытия: Requirement → Candidate → supported/unsupported.
   H4 (rounds>1): дополнительный целевой поиск по непокрытым требованиям,
   затем явная пометка недостающего. Ограничение раундов — конфигурацией.
"""

import time

from .parent_expansion import expand_parents, load_clause_store
from .query_analysis import local_llm_decompose

SUPPORTED_SCORE = -2.0


def plan_subtasks(question, use_llm=True):
    if use_llm:
        tasks, status = local_llm_decompose(question, with_status=True)
        return [task.text for task in tasks], status
    return [question], "single"


def _candidate_key(document):
    return document.meta.get("chunk_id") or document.id


def multi_hop_search(retriever, question, effective, metadata, timings):
    """Возвращает итоговый контекст (список Document)."""
    settings = effective["retrieval"]
    started = time.perf_counter()
    subtasks, plan_status = plan_subtasks(question, use_llm=True)
    timings["multi_hop_plan"] = time.perf_counter() - started
    rounds = settings.get("multi_hop_rounds", 1)
    candidate_top_k = settings["candidate_top_k"]

    merged = {}
    origin = {}
    diagnostics = {"plan_status": plan_status, "subtasks": [], "rounds": []}

    def run_round(queries, round_index):
        started_round = time.perf_counter()
        for query in queries:
            _, _, candidates, _ = retriever._hybrid_search(query, effective)
            reranked = retriever._rerank(query, list(candidates))[:candidate_top_k]
            for rank, document in enumerate(reranked, 1):
                key = _candidate_key(document)
                score = document.meta.get("rerank_score", 0.0)
                if key not in merged or score > merged[key].meta.get("rerank_score", 0.0):
                    merged[key] = document
                origin.setdefault(key, set()).add(query)
        diagnostics["rounds"].append({"round": round_index, "seconds": time.perf_counter() - started_round, "candidates": len(merged)})

    run_round([question] + [subtask for subtask in subtasks if subtask != question], 0)

    ordered = sorted(merged.values(), key=lambda document: document.meta.get("rerank_score", 0.0), reverse=True)
    coverage = []
    for subtask in subtasks:
        best = max((document for document in ordered if subtask in origin.get(_candidate_key(document), set())), key=lambda document: document.meta.get("rerank_score", 0.0), default=None)
        coverage.append({"requirement": subtask, "supported": bool(best and best.meta.get("rerank_score", 0.0) > SUPPORTED_SCORE), "best_score": best.meta.get("rerank_score", 0.0) if best else None})
    diagnostics["subtasks"] = coverage

    if rounds > 1:
        unsupported = [item["requirement"] for item in coverage if not item["supported"]]
        if unsupported:
            run_round(unsupported, 1)
            ordered = sorted(merged.values(), key=lambda document: document.meta.get("rerank_score", 0.0), reverse=True)
            for item in coverage:
                if item["supported"]:
                    continue
                best = max((document for document in ordered if item["requirement"] in origin.get(_candidate_key(document), set())), key=lambda document: document.meta.get("rerank_score", 0.0), default=None)
                if best and best.meta.get("rerank_score", 0.0) > SUPPORTED_SCORE:
                    item["supported"] = True
                    item["best_score"] = best.meta.get("rerank_score", 0.0)
                    item["recovered_in_round"] = 1
    diagnostics["unsupported_after_rounds"] = [item["requirement"] for item in coverage if not item["supported"]]

    if settings.get("parent_expansion"):
        if not hasattr(retriever, "_clause_store"):
            retriever._clause_store = load_clause_store()
        selected = expand_parents(ordered[: settings["output_top_k"] * 2], retriever._clause_store, settings["context_token_budget"], related_clauses=settings.get("related_clauses", False))
    else:
        selected = ordered[: settings["output_top_k"]]
    timings["multi_hop_total"] = time.perf_counter() - started
    metadata["multi_hop"] = diagnostics
    return selected
