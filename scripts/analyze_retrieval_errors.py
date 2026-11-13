import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.evaluation.error_analysis import analyze_reports
from navigator.settings import ROOT


CATEGORIES = ["Parsing Error", "Chunking Error", "Candidate Retrieval Error", "Fusion Error", "Reranking Error", "Selection Error", "Decomposition Error", "Insufficient Context Budget", "Gold Annotation Issue"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", default="baseline_holdout")
    parser.add_argument("--stable", default="stable_holdout")
    parser.add_argument("--split", default="holdout")
    parser.add_argument("--output", default=str(ROOT / "reports" / "retrieval_v3" / "01_error_analysis.md"))
    args = parser.parse_args()
    root = ROOT / "reports" / "retrieval_experiments"
    baseline = json.loads((root / args.baseline / "per_query_results.json").read_text(encoding="utf-8"))
    stable = json.loads((root / args.stable / "per_query_results.json").read_text(encoding="utf-8"))
    cases = json.loads((ROOT / "data" / f"retrieval_eval_{args.split}.json").read_text(encoding="utf-8"))["queries"]
    chunks = json.loads((ROOT / "data" / "chunks.json").read_text(encoding="utf-8"))
    source_rows = json.loads((ROOT / "data" / "source_documents.json").read_text(encoding="utf-8"))
    sources = {row["document_id"]: row["text"] for row in source_rows}
    analysis = analyze_reports(baseline, stable, cases, chunks, sources=sources)
    lines = ["# Retrieval v3 — детальный аудит ошибок", "", "## Проверка метрики", "", f"- {analysis['metrics_audit']['fragment_mrr_ndcg']}.", f"- {analysis['metrics_audit']['evidence_recall_at_6']}.", f"- {analysis['metrics_audit']['document_metrics']}.", f"- {analysis['metrics_audit']['overlap_rule']}.", "- Gold spans используются только в offline-анализе и не передаются в рабочий retrieval.", "", "## Baseline и stable по вопросам", "", "| Question ID | Answerable | Baseline Recall | Stable Recall | Изменение | Причина по gold groups |", "|---|---|---:|---:|---:|---|"]
    for row in analysis["questions"]:
        reasons = sorted({group["category"] for group in row["groups"] if group["category"]})
        if not row["answerable"]:
            reasons = ["не входит в evidence-знаменатель"]
        if not reasons and row["delta"] is not None and row["delta"] > 0:
            reasons = ["дополнительное покрытие после декомпозиции/selection"]
        if not reasons:
            reasons = ["нет новой ошибки" if row["stable_recall"] == 1 else "сохранённая ошибка требует ручной проверки"]
        def fmt(value):
            return "—" if value is None else f"{value:.4f}"
        lines.append(f"| {row['question_id']} | {row['answerable']} | {fmt(row['baseline_recall'])} | {fmt(row['stable_recall'])} | {fmt(row['delta'])} | {', '.join(reasons)} |")
    lines.extend(["", "## Классификация ошибок", "", "| Категория | Количество gold groups |", "|---|---:|"])
    for category in CATEGORIES:
        lines.append(f"| {category} | {analysis['category_counts'].get(category, 0)} |")
    lines.extend(["", "## Доказательства по ошибкам", "", "| Question/group | Категория | BM25 | Dense | RRF | Rerank | Selected | Chunk IDs |", "|---|---|---:|---:|---:|---:|---:|---|"])
    for row in analysis["questions"]:
        for group in row["groups"]:
            if not group["category"]:
                continue
            values = group["coverage_by_stage"]
            lines.append(f"| {row['question_id']}/{group['group_id']} | {group['category']} | {values['bm25']:.2f} | {values['dense']:.2f} | {values['rrf']:.2f} | {values['cross_encoder']:.2f} | {values['selected_context']:.2f} | {', '.join(group['available_chunks'])} |")
    lines.extend(["", "## Oracle Analysis", "", "| Сценарий | Recall | All-Evidence Hit |", "|---|---:|---:|"])
    for method in ("baseline", "stable"):
        for oracle, values in analysis["oracle"][method].items():
            lines.append(f"| {method}: {oracle} | {values['mean']:.4f} | {values['all_evidence_hit']:.4f} |")
    direct = analysis["oracle"]["oracle_d_direct_gold"]
    lines.append(f"| Oracle D: прямой gold при том же бюджете | {direct['mean']:.4f} | {direct['all_evidence_hit']:.4f} |")
    lines.extend(["", "## Приоритеты", "", f"- Candidate Retrieval Error: {analysis['category_counts'].get('Candidate Retrieval Error', 0)} gold groups; требуется улучшать нахождение кандидатов, а не усложнять selector.", f"- Fusion Error: {analysis['category_counts'].get('Fusion Error', 0)} gold groups; проверить потерю при top-20 RRF и расширение candidate pool.", f"- Selection/Budget: {analysis['category_counts'].get('Selection Error', 0)} / {analysis['category_counts'].get('Insufficient Context Budget', 0)}; увеличение бюджета по текущим ошибкам не обосновано.", f"- Stable ухудшил baseline на {len(analysis['stable_regressions'])} вопросах: {analysis['stable_regressions']}.", "- Oracle использует gold только в offline-отчёте. Прямой Oracle D — потолок метрики, а не рабочий поиск.", ""])
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    output.with_suffix(".json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
