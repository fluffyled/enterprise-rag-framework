"""Групповой bootstrap CI для разницы метрик rag100 между конфигурациями.

Вопросы, ссылающиеся на один gold source-unit (или один документ), статистически
зависимы — резampling выполняется по группам, а не по отдельным вопросам.
Метрики считаются по selected-предсказаниям их скрипта evaluate_retrieval.py.
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "reports" / "retrieval_experiments" / "rag100"
RAG = ROOT / "data" / "rag100"


def load_predictions(name, split):
    return {json.loads(line)["id"]: json.loads(line)["retrieved"] for line in (D / f"_{name}_{split}.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()}


def ranks_for(gold_rows, predictions):
    doc_rank, unit_rank = {}, {}
    for g in gold_rows:
        retr = predictions.get(g["id"], [])
        gold_docs = set(g["gold_document_ids"])
        typ = "page" if g["gold_location"]["type"] == "pdf_page" else "paragraph"
        want = str(g["gold_location"][typ])
        doc_hit = unit_hit = None
        for index, r in enumerate(retr, 1):
            if r["document_id"] in gold_docs and doc_hit is None:
                doc_hit = index
            if r["document_id"] == g["gold_document_id"] and r["unit_type"] == typ and str(r["unit_locator"]) == want and unit_hit is None:
                unit_hit = index
        doc_rank[g["id"]] = doc_hit
        unit_rank[g["id"]] = unit_hit
    return doc_rank, unit_rank


def metric_value(ranks, kind):
    values = []
    for rank in ranks.values():
        if kind.endswith("hit@5"):
            values.append(1.0 if rank is not None and rank <= 5 else 0.0)
        elif kind.endswith("hit@1"):
            values.append(1.0 if rank == 1 else 0.0)
        else:
            values.append(1.0 / rank if rank is not None and rank <= 10 else 0.0)
    return values


def grouped_bootstrap(left_ranks, right_ranks, kind, groups, iterations=2000, seed=42):
    rng = random.Random(seed)
    ids = list(left_ranks)
    grouped = defaultdict(list)
    for qid in ids:
        grouped[groups[qid]].append(qid)
    group_keys = sorted(grouped)
    values = {qid: (metric_value({qid: left_ranks[qid]}, kind)[0], metric_value({qid: right_ranks[qid]}, kind)[0]) for qid in ids}
    diffs = []
    for _ in range(iterations):
        picked = [rng.choice(group_keys) for _ in group_keys]
        sample = [qid for key in picked for qid in grouped[key]]
        left = sum(values[qid][0] for qid in sample)
        right = sum(values[qid][1] for qid in sample)
        diffs.append(left / len(sample) - right / len(sample))
    diffs.sort()
    return {
        "difference": sum(values[q][0] for q in ids) / len(ids) - sum(values[q][1] for q in ids) / len(ids),
        "ci95": [diffs[int(0.025 * iterations)], diffs[int(0.975 * iterations)]],
        "iterations": iterations,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="test")
    parser.add_argument("--pairs", default="BGE_e2:V2_stable,V2_stable:B0_baseline,V2_mmr:B0_baseline,V3F_final:B0_baseline")
    parser.add_argument("--output", default=str(ROOT / "reports" / "retrieval_experiments" / "rag100" / "grouped_bootstrap.json"))
    args = parser.parse_args()

    gold = [json.loads(line) for line in (RAG / "rag_gold_qa.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    gold_rows = [g for g in gold if g["answerable"] and g["split"] == args.split]
    unit_groups, doc_groups = {}, {}
    for g in gold_rows:
        typ = "page" if g["gold_location"]["type"] == "pdf_page" else "paragraph"
        unit_groups[g["id"]] = f"{g['gold_document_id']}:{typ}:{g['gold_location'][typ]}"
        doc_groups[g["id"]] = g["gold_document_id"]

    result = {"split": args.split, "n": len(gold_rows), "pairs": {}}
    for pair in args.pairs.split(","):
        left_name, right_name = pair.split(":")
        left_pred = load_predictions(f"{left_name}_selected", args.split)
        right_pred = load_predictions(f"{right_name}_selected", args.split)
        left_doc, left_unit = ranks_for(gold_rows, left_pred)
        right_doc, right_unit = ranks_for(gold_rows, right_pred)
        entry = {}
        for label, groups in (("by_unit", unit_groups), ("by_document", doc_groups)):
            entry[label] = {
                "doc_hit@5": grouped_bootstrap(left_doc, right_doc, "doc_hit@5", groups),
                "doc_mrr@10": grouped_bootstrap(left_doc, right_doc, "doc_mrr@10", groups),
                "unit_hit@5": grouped_bootstrap(left_unit, right_unit, "unit_hit@5", groups),
                "unit_mrr@10": grouped_bootstrap(left_unit, right_unit, "unit_mrr@10", groups),
            }
        result["pairs"][f"{left_name} - {right_name}"] = entry
        for label in entry:
            for metric, values in entry[label].items():
                print(f"{left_name} - {right_name} [{label}] {metric}: {values['difference']:+.4f} {values['ci95']}")
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
