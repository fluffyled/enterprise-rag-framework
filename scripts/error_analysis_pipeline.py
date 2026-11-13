"""Единый error-analysis pipeline (этап 6).

Классификация каждого ошибочного вопроса по этапу возникновения ошибки:
1. retrieval_miss — правильного документа нет среди кандидатов;
2. unit_miss — документ найден, правильный фрагмент (source-unit) не найден;
3. ranking_error — фрагмент найден, но расположен слишком низко (не в top-6);
4. selection_error — фрагмент был среди кандидатов top-6, но удалён селектором;
5. generation_error — информация была в контексте, LLM ответила неправильно;
6. citation_error — ответ правильный, но ссылка на источник неверная;
7. false_abstention — ответ существует, но модель отказалась;
8. unsupported_answer — ответ не подтверждён контекстом.

Вход: каталог end-to-end эксперимента (per_query_results.json) + predictions
candidates/selected для retrieval-стадий (опционально, rag100).
"""

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAG_PRED = ROOT / "reports/retrieval_experiments/rag100"


def load_predictions(name, split):
    path = RAG_PRED / f"_{name}_{split}.jsonl"
    if not path.exists():
        return None
    return {json.loads(line)["id"]: json.loads(line)["retrieved"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def gold_unit_key(gold_by_id, qid):
    g = gold_by_id.get(qid)
    if not g or not g.get("answerable"):
        return None
    loc = g["gold_location"]
    typ = "page" if loc["type"] == "pdf_page" else "paragraph"
    return g["gold_document_id"], typ, str(loc[typ])


def classify_row(row, gold_by_id, candidates, selected):
    qid = row["id"]
    g = gold_by_id.get(qid)
    answerable = row.get("answerable", True)
    result = row["result"]
    status = result.get("status")
    if not answerable:
        if status == "insufficient":
            return "ok"
        return "unsupported_answer"
    if status == "insufficient":
        return "false_abstention"
    if not row.get("candidate_all_evidence", True):
        return "retrieval_miss"
    if not row.get("context_all_evidence", True):
        key = gold_unit_key(gold_by_id, qid)
        if key and candidates and selected:
            in_cand = any((r["document_id"], r["unit_type"], str(r["unit_locator"])) == key for r in candidates.get(qid, []))
            in_sel = any((r["document_id"], r["unit_type"], str(r["unit_locator"])) == key for r in selected.get(qid, []))
            if in_sel:
                return "generation_error"
            if in_cand:
                return "selection_error"
            return "ranking_error" if any(r["document_id"] == key[0] for r in candidates.get(qid, [])) else "unit_miss"
        return "selection_error"
    metrics = row.get("answer_metrics", {})
    if metrics.get("answer_correctness_proxy"):
        return "ok"
    if metrics.get("citation_recall_proxy") == 1.0 and metrics.get("citation_precision_proxy", 1.0) < 1.0:
        return "citation_error"
    return "generation_error"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment-dir", required=True)
    parser.add_argument("--predictions", default=None, help="префикс predictions rag100, напр. BGE_rerank")
    parser.add_argument("--split", default="test")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    experiment_dir = Path(args.experiment_dir)
    rows = json.loads((experiment_dir / "per_query_results.json").read_text(encoding="utf-8"))
    gold_by_id = {g["id"]: g for g in (json.loads(line) for line in (ROOT / "data/rag100/rag_gold_qa.jsonl").read_text(encoding="utf-8").splitlines() if line.strip())}
    candidates = load_predictions(f"{args.predictions}_candidates", args.split) if args.predictions else None
    selected = load_predictions(f"{args.predictions}_selected", args.split) if args.predictions else None

    classified = []
    for row in rows:
        gold_row = gold_by_id.get(row["id"])
        if gold_row and gold_row.get("split") == "dev":
            continue
        category = classify_row(row, gold_by_id, candidates, selected)
        classified.append({"id": row["id"], "category": category, "status": row["result"].get("status")})
    counts = Counter(item["category"] for item in classified)
    payload = {"experiment": experiment_dir.name, "counts": dict(counts), "rows": classified}
    output = Path(args.output) if args.output else experiment_dir / "error_analysis.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [f"# Error analysis: {experiment_dir.name}", "", "| Категория | Количество |", "|---|---:|"]
    for category in ("ok", "retrieval_miss", "unit_miss", "ranking_error", "selection_error", "generation_error", "citation_error", "false_abstention", "unsupported_answer"):
        lines.append(f"| {category} | {counts.get(category, 0)} |")
    errors = [item for item in classified if item["category"] != "ok"]
    lines += ["", "## Ошибочные вопросы", "", "| ID | Категория | Status |", "|---|---|---|"]
    for item in errors:
        lines.append(f"| {item['id']} | {item['category']} | {item['status']} |")
    md = output.with_suffix(".md")
    md.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(dict(counts), ensure_ascii=False))
    print(output)


if __name__ == "__main__":
    main()
