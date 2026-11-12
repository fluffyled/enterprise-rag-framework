import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.settings import ROOT


NAMES = [
    "baseline_dev", "baseline_holdout", "stable_dev", "stable_holdout",
    "hierarchy_h1_dev", "hierarchy_h2_dev", "hierarchy_h3_dev",
    "contextual_c1_dev", "contextual_c2_dev", "contextual_c3_dev",
    "coverage_dedup_dev", "coverage_mmr_dev", "coverage_greedy_dev", "coverage_decomposed_dev",
    "adaptive_always_dev", "adaptive_rules_dev", "adaptive_coverage_dev",
    "graph_refs_dev", "graph_amendments_dev", "graph_depth2_dev", "graph_coverage_dev",
    "bge_e1_dev", "bge_e2_dev", "bge_e3_dev", "bge_e4_dev", "bge_e4_weighted_dev", "bge_e1_coverage_dev", "bge_e2_holdout",
    "multidoc2dial_pilot", "legalbench_pilot", "miracl_pilot",
]
KEYS = ["document_recall@5", "document_recall@10", "document_mrr@10", "document_ndcg@10", "evidence_recall@6", "all_evidence_hit@6", "mrr@10", "ndcg@10", "gold_span_coverage", "redundancy_ratio", "all_evidence_hit@6_errors"]


def main():
    result = {"schema_version": 1, "privacy": "aggregates only", "experiments": {}}
    for name in NAMES:
        directory = ROOT / "reports" / "retrieval_experiments" / name
        metrics_path = directory / "metrics.json"
        latency_path = directory / "latency.json"
        if not metrics_path.exists():
            continue
        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics = payload["metrics"]
        latency = json.loads(latency_path.read_text(encoding="utf-8")) if latency_path.exists() else {}
        result["experiments"][name] = {
            "dataset": payload["dataset"],
            "metrics": {key: metrics.get(key) for key in KEYS if key in metrics},
            "median_retrieval_seconds": latency.get("total", {}).get("median"),
            "index_bytes": payload.get("index_bytes"),
            "peak_rss_bytes": payload.get("resources", {}).get("peak_rss_bytes"),
        }
    output = ROOT / "metrics" / "retrieval_research_summary.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
