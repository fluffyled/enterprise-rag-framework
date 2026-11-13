import argparse
import json
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.evaluation.metrics import paired_bootstrap
from navigator.settings import ROOT


def load_experiment(path):
    path = Path(path)
    metrics_file = path / "metrics.json"
    payload = json.loads(metrics_file.read_text(encoding="utf-8"))
    per_query_path = path / "per_query_results.json"
    per_query = json.loads(per_query_path.read_text(encoding="utf-8")) if per_query_path.exists() else []
    latency_path = path / "latency.json"
    latency = json.loads(latency_path.read_text(encoding="utf-8")) if latency_path.exists() else {}
    config_path = path / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    return {"name": path.name, "path": path, **payload, "per_query": per_query, "latency": latency, "config": config}


def plot_metric(experiments, metric, output, title):
    names = [experiment["name"] for experiment in experiments]
    values = [experiment["metrics"].get(metric, 0) or 0 for experiment in experiments]
    fig, ax = plt.subplots(figsize=(max(7, len(names) * 1.4), 4))
    ax.bar(names, values)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel(metric)
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(output, dpi=150)
    plt.close(fig)


def make_plots(experiments, output):
    plot_metric(experiments, "document_recall@5", output / "document_recall.png", "Document Recall@5")
    plot_metric(experiments, "evidence_recall@6", output / "evidence_recall.png", "Evidence Recall@6")
    plot_metric(experiments, "all_evidence_hit@6", output / "all_evidence_hit.png", "All-Evidence Hit@6")
    plot_metric(experiments, "ndcg@10", output / "ndcg.png", "nDCG@10")
    fig, ax = plt.subplots(figsize=(7, 5))
    for experiment in experiments:
        latency = experiment["latency"].get("total", {}).get("median", 0)
        quality = experiment["metrics"].get("evidence_recall@6") or experiment["metrics"].get("document_recall@5") or 0
        ax.scatter(latency, quality, label=experiment["name"])
        ax.annotate(experiment["name"], (latency, quality))
    ax.set_xlabel("Median retrieval latency, seconds")
    ax.set_ylabel("Quality")
    ax.set_title("Quality vs Retrieval Latency")
    fig.tight_layout()
    fig.savefig(output / "quality_vs_latency.png", dpi=150)
    plt.close(fig)
    types = sorted({row.get("question_type") for experiment in experiments for row in experiment["per_query"] if row.get("question_type")})
    if types:
        fig, ax = plt.subplots(figsize=(max(8, len(types) * 1.5), 5))
        width = 0.8 / len(experiments)
        for index, experiment in enumerate(experiments):
            values = []
            for question_type in types:
                rows = [row for row in experiment["per_query"] if row.get("question_type") == question_type and row["metrics"].get("evidence_recall@6") is not None]
                values.append(sum(row["metrics"]["evidence_recall@6"] for row in rows) / len(rows) if rows else 0)
            positions = [position + index * width for position in range(len(types))]
            ax.bar(positions, values, width=width, label=experiment["name"])
        ax.set_xticks([position + 0.4 for position in range(len(types))], types, rotation=25)
        ax.set_ylim(0, 1.05)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output / "quality_by_question_type.png", dpi=150)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 5))
    for experiment in experiments:
        budgets = experiment["config"].get("config", {}).get("retrieval", {}).get("context_token_budget", 2000)
        coverage = experiment["metrics"].get("gold_span_coverage", 0) or 0
        ax.scatter(budgets, coverage, label=experiment["name"])
        ax.annotate(experiment["name"], (budgets, coverage))
    ax.set_xlabel("Context token budget")
    ax.set_ylabel("Gold-span coverage")
    ax.set_title("Context size vs Evidence Coverage")
    fig.tight_layout()
    fig.savefig(output / "context_size_coverage.png", dpi=150)
    plt.close(fig)
    if len(experiments) >= 2:
        baseline, current = experiments[0], experiments[-1]
        ids = sorted({row["id"] for row in baseline["per_query"]} & {row["id"] for row in current["per_query"]})
        matrix = [[0, 0], [0, 0]]
        left = {row["id"]: row for row in baseline["per_query"]}
        right = {row["id"]: row for row in current["per_query"]}
        for query_id in ids:
            a = left[query_id]["metrics"].get("all_evidence_hit@6")
            b = right[query_id]["metrics"].get("all_evidence_hit@6")
            if a is not None and b is not None:
                matrix[int(bool(a))][int(bool(b))] += 1
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.imshow(matrix, cmap="Blues")
        for i in range(2):
            for j in range(2):
                ax.text(j, i, matrix[i][j], ha="center", va="center")
        ax.set_xticks([0, 1], ["miss", "hit"])
        ax.set_yticks([0, 1], ["miss", "hit"])
        ax.set_xlabel(current["name"])
        ax.set_ylabel(baseline["name"])
        ax.set_title("Per-query error transition matrix")
        fig.tight_layout()
        fig.savefig(output / "error_transition_matrix.png", dpi=150)
        plt.close(fig)
        coverage_rows = []
        for query_id in ids:
            pair = []
            for row in (left[query_id], right[query_id]):
                total = row["metrics"].get("requirements_total") or 0
                pair.append(row["metrics"].get("covered_requirements", 0) / total if total else 0)
            coverage_rows.append(pair)
        if coverage_rows:
            fig, ax = plt.subplots(figsize=(5, max(4, len(coverage_rows) * 0.2)))
            ax.imshow(coverage_rows, aspect="auto", vmin=0, vmax=1, cmap="YlGn")
            ax.set_xticks([0, 1], [baseline["name"], current["name"]])
            ax.set_yticks(range(len(ids)), ids, fontsize=6)
            ax.set_title("Gold requirement coverage by query")
            fig.tight_layout()
            fig.savefig(output / "coverage_requirements.png", dpi=150)
            plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("experiments", nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--bootstrap", type=int, default=2000)
    args = parser.parse_args()
    experiments = [load_experiment(ROOT / "reports" / "retrieval_experiments" / value if not Path(value).exists() else Path(value)) for value in args.experiments]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    keys = sorted(set().union(*(experiment["metrics"].keys() for experiment in experiments)))
    lines = ["# Experiment comparison", "", "| Metric | " + " | ".join(experiment["name"] for experiment in experiments) + " |", "|---|" + "---:|" * len(experiments)]
    for key in keys:
        if key.endswith("_n"):
            continue
        lines.append("| " + key + " | " + " | ".join(f"{experiment['metrics'].get(key):.6f}" if isinstance(experiment["metrics"].get(key), float) else str(experiment["metrics"].get(key, "—")) for experiment in experiments) + " |")
    lines.append("| median latency (s) | " + " | ".join(f"{experiment['latency'].get('total', {}).get('median', 0):.6f}" for experiment in experiments) + " |")
    lines.append("| index bytes | " + " | ".join(str(experiment.get("index_bytes", "—")) for experiment in experiments) + " |")
    distributions = {}
    for experiment in experiments:
        distributions[experiment["name"]] = {}
        for metric in ("document_recall@5", "evidence_recall@6", "all_evidence_hit@6", "mrr@10", "ndcg@10", "gold_span_coverage"):
            values = [row["metrics"][metric] for row in experiment["per_query"] if row["metrics"].get(metric) is not None]
            distributions[experiment["name"]][metric] = {"mean": statistics.fmean(values), "median": statistics.median(values), "n": len(values)} if values else {"mean": None, "median": None, "n": 0}
    paired = {}
    transitions = {}
    pairwise = {}
    if len(experiments) >= 2:
        left = {row["id"]: row["metrics"] for row in experiments[0]["per_query"]}
        for experiment in experiments[1:]:
            right = {row["id"]: row["metrics"] for row in experiment["per_query"]}
            common = sorted(left.keys() & right.keys())
            current_paired = {}
            current_transitions = {}
            for metric in ("document_recall@5", "evidence_recall@6", "all_evidence_hit@6", "ndcg@10", "gold_span_coverage"):
                current_paired[metric] = paired_bootstrap([left[key] for key in common], [right[key] for key in common], metric, iterations=args.bootstrap)
                values = [(left[key].get(metric), right[key].get(metric)) for key in common]
                values = [(a, b) for a, b in values if a is not None and b is not None]
                current_transitions[metric] = {"improved": sum(b > a for a, b in values), "regressed": sum(b < a for a, b in values), "unchanged": sum(b == a for a, b in values), "n": len(values)}
            pairwise[experiment["name"]] = {"paired_bootstrap": current_paired, "transitions": current_transitions}
        paired = pairwise[experiments[-1]["name"]]["paired_bootstrap"]
        transitions = pairwise[experiments[-1]["name"]]["transitions"]
    if paired:
        lines.extend(["", "## Paired bootstrap: last minus baseline", "", "| Metric | Difference | 95% CI | n |", "|---|---:|---|---:|"])
        for metric, result in paired.items():
            lines.append(f"| {metric} | {result.get('difference')} | {result.get('ci95')} | {result['n']} |")
    if transitions:
        lines.extend(["", "## Per-query transitions", "", "| Metric | Improved | Regressed | Unchanged |", "|---|---:|---:|---:|"])
        for metric, result in transitions.items():
            lines.append(f"| {metric} | {result['improved']} | {result['regressed']} | {result['unchanged']} |")
    (output / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (output / "comparison.json").write_text(json.dumps({"experiments": [{"name": experiment["name"], "metrics": experiment["metrics"], "latency": experiment["latency"]} for experiment in experiments], "paired_bootstrap": paired, "transitions": transitions, "pairwise_vs_baseline": pairwise, "quality_distributions": distributions}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "config.json").write_text(json.dumps({experiment["name"]: experiment["config"] for experiment in experiments}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps({experiment["name"]: experiment["metrics"] for experiment in experiments}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "per_query_results.json").write_text(json.dumps({experiment["name"]: experiment["per_query"] for experiment in experiments}, ensure_ascii=False), encoding="utf-8")
    (output / "latency.json").write_text(json.dumps({experiment["name"]: experiment["latency"] for experiment in experiments}, ensure_ascii=False, indent=2), encoding="utf-8")
    errors = ["# Quality errors", ""]
    for experiment in experiments:
        failed = [row["id"] for row in experiment["per_query"] if row["metrics"].get("all_evidence_hit@6") == 0]
        errors.append(f"- {experiment['name']}: {len(failed)} evidence errors; ids={failed}")
    (output / "errors.md").write_text("\n".join(errors) + "\n", encoding="utf-8")
    make_plots(experiments, output)
    print(output)


if __name__ == "__main__":
    main()
