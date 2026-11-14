"""Measure the connected application against local complex50 and rag100 questions."""
import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median, quantiles
from time import perf_counter

from navigator.rag_service import ask, index_path
from scripts.evaluate_generation_v2 import proxy_hits
from scripts.run_selected_generation import load_cases


def summarize(rows):
    for dataset in ("complex50", "rag100"):
        group = [row for row in rows if row["dataset"] == dataset]
        if not group:
            continue
        answerable = [row for row in group if row["answerable"]]
        unanswerable = [row for row in group if not row["answerable"]]
        print(json.dumps({
            "dataset": dataset,
            "questions": len(group),
            "statuses": dict(Counter(row["status"] for row in group)),
            "lexical_matches": sum(row["hits"] for row in answerable),
            "reference_items": sum(row["total"] for row in answerable),
            "all_reference_items_matched": sum(row["total"] > 0 and row["hits"] == row["total"] for row in answerable),
            "abstained_on_answerable": sum(row["status"] == "insufficient" for row in answerable),
            "correct_abstentions": sum(row["status"] == "insufficient" for row in unanswerable),
            "unanswerable": len(unanswerable),
            "quotes_checked": sum(row["quotes"] for row in group),
            "invalid_quotes": sum(row["invalid_quotes"] for row in group),
            "latency_p50_s": round(median(row["seconds"] for row in group), 3),
            "latency_p95_s": round(quantiles([row["seconds"] for row in group], n=20, method="inclusive")[-1], 3)
            if len(group) > 1 else group[0]["seconds"],
        }))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--retrieval", choices=("fast", "quality"), default="fast")
    parser.add_argument("--generation", choices=("legacy", "g2"), default="legacy")
    parser.add_argument("--case", action="append", help="Limit to these question IDs")
    parser.add_argument("--summary", action="store_true", help="Summarize the existing output file")
    parser.add_argument("--retry-from", type=Path, help="Copy successful rows and rerun failed or missing questions")
    args = parser.parse_args()
    if args.summary:
        summarize([json.loads(line) for line in args.output.read_text(encoding="utf-8").splitlines()])
        return
    cases = [(dataset, case) for dataset, case in load_cases() if not args.case or case["id"] in args.case]
    if not cases or (args.case and set(args.case) != {case["id"] for _, case in cases}):
        parser.error("Unknown or missing evaluation case")
    if not index_path().is_file():
        parser.error("Set NAVIGATOR_INDEX to a compatible BGE index")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    previous = {}
    if args.retry_from:
        for line in args.retry_from.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if (row.get("retrieval", args.retrieval), row.get("generation", args.generation)) != (
                args.retrieval, args.generation
            ):
                parser.error("Retry input uses different evaluation modes")
            if row["status"] != "error":
                previous[row["dataset"], row["id"]] = row
    rows = []
    with args.output.open("x", encoding="utf-8") as stream:
        for dataset, case in cases:
            prior = previous.get((dataset, case["id"]))
            if prior:
                rows.append(prior)
                stream.write(json.dumps(prior, ensure_ascii=False) + "\n")
                continue
            started = perf_counter()
            result = ask(case["question"], args.retrieval, args.generation)
            elapsed = round(perf_counter() - started, 3)
            expected = case["required_facts"] if dataset == "complex50" else (
                [{"fact_id": "reference", "text": case["reference_answer"]}] if case["answerable"] else [])
            items = result.summary + result.steps
            quotes = [(quote, src["excerpt"]) for src in result.sources for quote in src["quotes"]]
            row = {
                "dataset": dataset, "id": case["id"], "answerable": case["answerable"],
                "retrieval": args.retrieval, "generation": args.generation,
                "status": result.status, "seconds": elapsed, "total": len(expected),
                "hits": len(proxy_hits(expected, [item["text"] for item in items])),
                "quotes": len(quotes), "invalid_quotes": sum(quote not in excerpt for quote, excerpt in quotes),
                "error": result.error,
            }
            if result.status == "error" and result.diagnostics.get("transport_error"):
                raise RuntimeError(f"Local LLM is unavailable at {case['id']}; stopping the evaluation")
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(dataset, case["id"], result.status, elapsed, flush=True)
    summarize(rows)


if __name__ == "__main__":
    main()
