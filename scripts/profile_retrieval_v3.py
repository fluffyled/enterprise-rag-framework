import argparse
import json
import statistics
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.settings import ROOT


def correlation(left, right):
    if len(left) < 2 or len(set(left)) < 2 or len(set(right)) < 2:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def profile(path):
    path = Path(path)
    rows = json.loads((path / "per_query_results.json").read_text(encoding="utf-8"))
    latency = json.loads((path / "latency.json").read_text(encoding="utf-8"))
    metrics = json.loads((path / "metrics.json").read_text(encoding="utf-8"))
    totals = [row["repeat_timings"][0]["total"] for row in rows]
    subtasks = [len(row["trace"]["metadata"].get("subtasks", [])) for row in rows]
    candidates = [len(row["trace"]["stages"].get("cross_encoder", [])) for row in rows]
    query_counts = [max(1, count) + int(count > 1) for count in subtasks]
    rerank_pairs = [candidate_count * query_count for candidate_count, query_count in zip(candidates, query_counts)]
    questions = [row.get("question") for row in rows if row.get("question")]
    result = {
        "name": path.name,
        "questions": len(rows),
        "latency": latency,
        "resources": metrics.get("resources"),
        "correlation_total_subtasks": correlation(totals, subtasks),
        "correlation_total_candidates": correlation(totals, candidates),
        "correlation_total_rerank_pairs": correlation(totals, rerank_pairs),
        "mean_subtasks": statistics.fmean(subtasks) if subtasks else 0,
        "mean_candidates": statistics.fmean(candidates) if candidates else 0,
        "duplicate_question_rate": 1 - len(set(questions)) / len(questions) if questions else None,
        "slowest": [{"id": row["id"], "total": row["repeat_timings"][0]["total"], "subtasks": len(row["trace"]["metadata"].get("subtasks", [])), "candidates": len(row["trace"]["stages"].get("cross_encoder", [])), "timings": row["repeat_timings"][0]} for row in sorted(rows, key=lambda item: item["repeat_timings"][0]["total"], reverse=True)[:10]],
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiments", nargs="+")
    parser.add_argument("--output", default=str(ROOT / "reports" / "retrieval_v3" / "04_performance.md"))
    args = parser.parse_args()
    profiles = [profile(ROOT / "reports" / "retrieval_experiments" / name) for name in args.experiments]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    (output.with_suffix(".json")).write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Retrieval v3 — профилирование производительности", "", "Замеры warm retrieval; cold initialization сохранён отдельно в latency.json каждого эксперимента.", "", "| Конфигурация | Медиана, с | Mean, с | p95, с | Подзадачи | Кандидаты | Corr(total, подзадачи) | Corr(total, CE pairs) |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for row in profiles:
        total = row["latency"].get("total", {})
        pairs = row["correlation_total_rerank_pairs"]
        lines.append(f"| {row['name']} | {total.get('median')} | {total.get('mean')} | {total.get('p95')} | {row['mean_subtasks']:.3f} | {row['mean_candidates']:.3f} | {row['correlation_total_subtasks']} | {pairs} |")
    for row in profiles:
        lines.extend(["", f"## {row['name']}: этапы", "", "| Этап | Медиана, с | Mean, с | p95, с |", "|---|---:|---:|---:|"])
        for stage, values in row["latency"].items():
            if values:
                lines.append(f"| {stage} | {values.get('median')} | {values.get('mean')} | {values.get('p95')} |")
        lines.extend(["", "### Наиболее дорогие запросы", "", "| Query | Total | Подзадачи | Кандидаты |", "|---|---:|---:|---:|"])
        for item in row["slowest"]:
            lines.append(f"| {item['id']} | {item['total']:.4f} | {item['subtasks']} | {item['candidates']} |")
        lines.extend(["", f"Duplicate question rate: {row['duplicate_question_rate']}. Exact-query cache полезен только при повторах; fingerprint индекса и модели обязателен.", ""])
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
