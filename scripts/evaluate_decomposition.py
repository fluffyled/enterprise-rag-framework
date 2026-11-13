import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.query_analysis import decompose_question, decompose_question_improved, local_llm_decompose
from navigator.settings import ROOT


def normalize_task(text):
    return text.strip().rstrip("?;.").strip()


def evaluate_method(cases, method):
    rows = []
    for case in cases:
        started = time.perf_counter()
        tasks = method(case["question"])
        elapsed = time.perf_counter() - started
        status = "rules"
        if isinstance(tasks, tuple):
            tasks, status = tasks
        texts = [task.text for task in tasks]
        normalized = [normalize_task(text) for text in texts]
        expected = [normalize_task(text) for text in case["expected"]]
        valid = all(case["question"][task.source_span["start"]:task.source_span["end"]] == task.text for task in tasks)
        rows.append({"id": case["id"], "exact_match": normalized == expected, "valid_spans": valid, "expected_count": len(case["expected"]), "actual_count": len(tasks), "actual": texts, "latency_seconds": elapsed, "planner_status": status})
    return {"cases": len(rows), "exact_match": sum(row["exact_match"] for row in rows) / len(rows), "valid_spans": sum(row["valid_spans"] for row in rows) / len(rows), "mean_subtasks": sum(row["actual_count"] for row in rows) / len(rows), "mean_latency_seconds": sum(row["latency_seconds"] for row in rows) / len(rows), "planner_fallback_rate": sum(row["planner_status"] == "fallback" for row in rows) / len(rows), "errors": [row["id"] for row in rows if not row["exact_match"] or not row["valid_spans"]], "per_query": rows}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--planner", action="store_true")
    parser.add_argument("--endpoint")
    args = parser.parse_args()
    cases = json.loads((ROOT / "data" / "decomposition_eval.json").read_text(encoding="utf-8"))
    result = {"D0": evaluate_method(cases, decompose_question), "D1": evaluate_method(cases, decompose_question_improved)}
    if args.planner:
        result["D2"] = evaluate_method(cases, lambda question: local_llm_decompose(question, endpoint=args.endpoint, with_status=True))
    output = ROOT / "reports" / "retrieval_v3" / "decomposition_rules.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: {metric: value for metric, value in row.items() if metric != "per_query"} for key, row in result.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
