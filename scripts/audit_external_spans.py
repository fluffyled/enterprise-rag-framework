import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.evaluation.datasets.legalbench import load_legalbench
from navigator.settings import ROOT


def audit(cases, chunks):
    by_document = {}
    for chunk in chunks:
        by_document.setdefault(chunk["meta"]["document_id"], []).append(chunk)
    coverages = []
    missing = []
    per_query = []
    for case in cases:
        query_values = []
        for group in case.get("evidence_groups", []):
            best = 0.0
            for gold in group.get("alternatives", []):
                gold_length = max(1, gold["end"] - gold["start"])
                for chunk in by_document.get(gold["document_id"], []):
                    span = chunk["meta"]["source_span"]
                    overlap = max(0, min(span["end"], gold["end"]) - max(span["start"], gold["start"]))
                    best = max(best, overlap / gold_length)
            coverages.append(best)
            query_values.append({"group_id": group["id"], "best_coverage": best})
            if best == 0:
                missing.append(case["id"])
        per_query.append({"id": case["id"], "groups": query_values})
    return {
        "gold_used_online": False,
        "queries": len(cases),
        "groups": len(coverages),
        "available_groups": sum(value > 0 for value in coverages),
        "unavailable_groups": sum(value == 0 for value in coverages),
        "full_span_groups": sum(value == 1 for value in coverages),
        "mean_oracle_span_coverage_all_chunks": statistics.fmean(coverages) if coverages else None,
        "missing_query_ids": sorted(set(missing)),
        "per_query": per_query,
    }


def main():
    parser = argparse.ArgumentParser(description="Offline Oracle доступности gold spans среди всех chunks")
    parser.add_argument("--chunks", required=True)
    parser.add_argument("--split", default="cuad")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--legal-data-dir")
    parser.add_argument("--output", default=str(ROOT / "reports" / "retrieval_v3" / "legalbench_chunk_oracle.json"))
    args = parser.parse_args()
    cases = load_legalbench(args.legal_data_dir, benchmark_name=args.split, query_limit=args.limit)["queries"]
    chunks = json.loads(Path(args.chunks).read_text(encoding="utf-8"))
    result = audit(cases, chunks)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "per_query"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
