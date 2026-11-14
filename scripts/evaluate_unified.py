"""Measure the connected application against local complex50 and rag100 questions."""
import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from statistics import median, quantiles
from time import perf_counter

from navigator.corpus import fingerprint
from navigator.rag_service import PROFILES, ask, index_path
from navigator.settings import DATA, ROOT


def run_fingerprint(cases, retrieval, generation):
    model = json.loads((ROOT / "answer-model.lock.json").read_text(encoding="utf-8"))
    model_path = ROOT / model["local_dir"] / model["filename"]
    files = [index_path(), PROFILES[retrieval], DATA / "source_documents.json",
             DATA / "clauses/clauses.json", ROOT / "models.lock.json", model_path]
    server = Path(os.environ.get("NAVIGATOR_EVAL_SERVER", ROOT / "tools/llama-cuda/llama-server.exe"))
    files.append(server)
    if not all(path.is_file() for path in files):
        raise ValueError("Evaluation requires local index, corpus, model and server artifacts")
    changes = subprocess.check_output(["git", "diff", "HEAD", "--", "navigator", "answering", "scripts"], cwd=ROOT)
    material = {
        "schema": 1, "revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "changes": hashlib.sha256(changes).hexdigest(), "evaluator": fingerprint(Path(__file__)),
        "artifacts": [fingerprint(path) for path in files], "cases": cases,
        "retrieval": retrieval, "generation": generation,
        "endpoint": os.environ.get("ANSWER_LLM_ENDPOINT" if generation == "g2" else "LLM_ENDPOINT"),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
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
    try:
        benchmark = run_fingerprint(cases, args.retrieval, args.generation)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    previous = {}
    if args.retry_from:
        for line in args.retry_from.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("benchmark") != benchmark:
                parser.error("Retry input belongs to a different benchmark or lacks a fingerprint")
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
                "benchmark": benchmark,
                "status": result.status, "seconds": elapsed, "total": len(expected),
                "hits": len(proxy_hits(expected, [item["text"] for item in items])),
                "quotes": len(quotes), "invalid_quotes": sum(quote not in excerpt for quote, excerpt in quotes),
                "error": result.error,
            }
            if result.status == "error" and result.diagnostics.get("transport_error"):
                reason = result.diagnostics.get("review_issues") or result.error
                raise RuntimeError(f"Local LLM is unavailable at {case['id']}: {reason}")
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            print(dataset, case["id"], result.status, elapsed, flush=True)
    summarize(rows)


if __name__ == "__main__":
    main()
