import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.settings import ROOT


SECTIONS = [("multidoc2dial", "MultiDoc2Dial — 300 validation queries / 488 documents"), ("legalbench", "LegalBench-RAG — 200 CUAD queries"), ("miracl", "MIRACL Russian — воспроизводимый multi-shard pilot")]


def error_summary(rows):
    has_evidence = any(row["metrics"].get("all_evidence_hit@6") is not None for row in rows)
    metric = "all_evidence_hit@6" if has_evidence else "all_documents_hit@5"
    failed = [row for row in rows if row["metrics"].get(metric) == 0]
    counts = {"no_gold_bm25": 0, "no_gold_dense": 0, "no_gold_rrf": 0, "no_gold_reranked": 0, "available_but_missed": 0}
    for row in failed:
        gold = set(row.get("gold_document_ids", []))
        stages = row["trace"]["stages"]
        present = {stage: bool(gold & {item.get("document_id") for item in stages.get(stage, [])}) for stage in ("bm25", "dense", "rrf", "cross_encoder")}
        for stage, key in (("bm25", "no_gold_bm25"), ("dense", "no_gold_dense"), ("rrf", "no_gold_rrf"), ("cross_encoder", "no_gold_reranked")):
            counts[key] += not present[stage]
        counts["available_but_missed"] += present["cross_encoder"]
    return {"metric": metric, "errors": len(failed), **counts}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-root", default="v3_external")
    parser.add_argument("--output", default=str(ROOT / "reports" / "retrieval_v3" / "02_external_benchmarks.md"))
    args = parser.parse_args()
    lines = ["# Retrieval v3 — расширенные внешние benchmarks", "", "Все сравнения парные. Разные языки и домены не объединяются в одну метрику. Полные параметры и графики находятся в связанных comparison-каталогах.", "", "Источники: [MultiDoc2Dial](https://github.com/IBM/multidoc2dial) и [описание данных](https://doc2dial.github.io/multidoc2dial/data_readme.html); [LegalBench-RAG](https://github.com/zeroentropy-ai/legalbenchrag) и [статья](https://arxiv.org/abs/2408.10343); [MIRACL](https://github.com/project-miracl/miracl) и [официальный сайт](https://project-miracl.github.io/).", ""]
    for directory, title in SECTIONS:
        comparison_path = ROOT / "reports" / "retrieval_experiments" / args.comparison_root / directory / "comparison.json"
        if not comparison_path.exists():
            raise FileNotFoundError(comparison_path)
        comparison = json.loads(comparison_path.read_text(encoding="utf-8"))
        lines.extend([f"## {title}", "", "| Конфигурация | Doc Recall@5 | Evidence Recall@6 | All-Evidence Hit@6 | MRR@10 | nDCG@10 | Медиана latency |", "|---|---:|---:|---:|---:|---:|---:|"])
        for experiment in comparison["experiments"]:
            metrics = experiment["metrics"]
            original_path = ROOT / "reports" / "retrieval_experiments" / experiment["name"] / "metrics.json"
            original = json.loads(original_path.read_text(encoding="utf-8"))
            dataset = original["dataset"]
            lines.append(f"| {experiment['name']} | {metrics.get('document_recall@5')} | {metrics.get('evidence_recall@6')} | {metrics.get('all_evidence_hit@6')} | {metrics.get('mrr@10')} | {metrics.get('ndcg@10')} | {experiment['latency'].get('total', {}).get('median')} |")
            lines.extend(["", f"Dataset metadata: `{json.dumps(dataset, ensure_ascii=False)}`", ""])
        lines.extend(["### Парное сравнение последней конфигурации с baseline", "", "| Метрика | Δ | 95% CI | Improved | Regressed |", "|---|---:|---|---:|---:|"])
        for metric, result in comparison.get("paired_bootstrap", {}).items():
            transition = comparison.get("transitions", {}).get(metric, {})
            lines.append(f"| {metric} | {result.get('difference')} | {result.get('ci95')} | {transition.get('improved')} | {transition.get('regressed')} |")
        lines.extend(["", "### Медианы качества по запросам", "", "| Конфигурация | Doc Recall@5 | Evidence Recall@6 | All-Evidence Hit@6 | MRR@10 | nDCG@10 |", "|---|---:|---:|---:|---:|---:|"])
        for name, distribution in comparison.get("quality_distributions", {}).items():
            lines.append(f"| {name} | {distribution['document_recall@5']['median']} | {distribution['evidence_recall@6']['median']} | {distribution['all_evidence_hit@6']['median']} | {distribution['mrr@10']['median']} | {distribution['ndcg@10']['median']} |")
        for name, paired in comparison.get("pairwise_vs_baseline", {}).items():
            if name == comparison["experiments"][-1]["name"]:
                continue
            lines.extend(["", f"### {name} против baseline", "", "| Метрика | Δ | 95% CI | Improved | Regressed |", "|---|---:|---:|---:|---:|"])
            for metric, result in paired.get("paired_bootstrap", {}).items():
                transition = paired.get("transitions", {}).get(metric, {})
                lines.append(f"| {metric} | {result.get('difference')} | {result.get('ci95')} | {transition.get('improved')} | {transition.get('regressed')} |")
        per_query = json.loads((comparison_path.parent / "per_query_results.json").read_text(encoding="utf-8"))
        lines.extend(["", "### Характерные ошибки", "", "Ниже `no gold` означает отсутствие gold-документа на указанном этапе среди запросов с итоговой ошибкой; `available but missed` — gold-документ дошёл до reranked candidates, но итоговая метрика не выполнена.", "", "| Конфигурация | Ошибки | Нет gold BM25 | Нет gold Dense | Нет gold RRF | Нет gold reranked | Available but missed |", "|---|---:|---:|---:|---:|---:|---:|"])
        for name, rows in per_query.items():
            summary = error_summary(rows)
            lines.append(f"| {name} | {summary['errors']} | {summary['no_gold_bm25']} | {summary['no_gold_dense']} | {summary['no_gold_rrf']} | {summary['no_gold_reranked']} | {summary['available_but_missed']} |")
        lines.extend(["", "Полные доказательства находятся в `errors.md` и per-query traces. Ошибки не смешиваются с другими датасетами.", ""])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
