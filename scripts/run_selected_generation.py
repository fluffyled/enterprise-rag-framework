"""Evaluate the selected G2 generator on all 150 questions, using Oracle evidence."""
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median, quantiles
from time import perf_counter
from urllib.request import ProxyHandler, build_opener
from zipfile import ZipFile

from answering.core import NoRedirect
from answering.v2 import AnswerInputV1, generate_v2
from answering.v2.pipeline import Settings
from scripts.evaluate_generation_v2 import oracle_input, proxy_hits

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path("reports/generation-research/g2-all150.jsonl")
ENDPOINT = "http://127.0.0.1:8091/v1/chat/completions"
SETTINGS = Settings(verify=False, input_chars=1900, max_output_tokens=1450,
                    preserve_alternatives=True)


def load_cases():
    pairs = (
        ("complex50", "hierarchical_rag_plan_and_dataset_50.zip", "hierarchical_complex_qa_50.jsonl"),
        ("rag100", "rag_eval_dataset_100.zip", "rag_gold_qa.jsonl"),
    )
    for dataset, filename, member in pairs:
        local = Path(__file__).resolve().parents[1] / "data" / ("hrag50" if dataset == "complex50" else "rag100") / member
        if local.exists():
            for line in local.read_text(encoding="utf-8-sig").splitlines():
                if line.strip():
                    yield dataset, json.loads(line)
            continue
        with ZipFile(ROOT / filename) as archive:
            for line in archive.read(member).splitlines():
                yield dataset, json.loads(line)


def get_input(dataset, case):
    if dataset == "complex50":
        return oracle_input(case), case["required_facts"]
    evidence = []
    gold = []
    if case["answerable"]:
        quote = case["evidence_quote"]
        start, end = case["evidence_start"], case["evidence_end"]
        evidence.append({
            "id": "RAG100:" + case["id"],
            "document_id": str(case["gold_document_id"]),
            "document_title": case["gold_document_filename"],
            "full_text": quote,
            "metadata": {"gold_location": case["gold_location"]},
            "source_spans": [[start, end]] if isinstance(start, int) and isinstance(end, int) and 0 <= start < end else [],
        })
        gold.append({"fact_id": "reference", "text": case["reference_answer"]})
    return AnswerInputV1(question=case["question"], evidence=evidence), gold


def main(output_path, repair_from=None, *, resume=False):
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open("http://127.0.0.1:8091/v1/models", timeout=10) as response:
        models = json.load(response)["data"]
    if len(models) != 1 or "qwen3.5-4b-q4_k_m" not in models[0]["id"].casefold():
        raise RuntimeError("Expected only Qwen3.5-4B-Q4_K_M")
    cases = [(dataset, case, *get_input(dataset, case)) for dataset, case in load_cases()]
    if len(cases) != 150 or len({(d, c["id"]) for d, c, *_ in cases}) != 150:
        raise ValueError("Expected 150 distinct dataset/question IDs")
    # Report known regressions early while preserving the full sample.
    priority = {"HQ004", "HQ014", "HQ022", "HQ048", "Q031", "Q032"}
    cases.sort(key=lambda row: row[1]["id"] not in priority)
    if repair_from:
        previous = read_rows(repair_from)
        expected = {(d, c["id"]) for d, c, *_ in cases}
        if len(previous) != 150 or {(r["dataset"], r["id"]) for r in previous} != expected:
            raise ValueError("Repair requires a complete source trace")
        failures = {(r["dataset"], r["id"]) for r in previous if r["result"]["status"] == "error"}
        cases = [row for row in cases if (row[0], row[1]["id"]) in failures]
    if resume:
        if repair_from:
            raise ValueError("Resume and repair require separate runs")
        previous = read_rows(output_path)
        expected = {(d, c["id"]): hashlib.sha256(r.model_dump_json().encode()).hexdigest()
                    for d, c, r, _ in cases}
        done = {(r["dataset"], r["id"]): r["input_sha256"] for r in previous}
        if len(done) != len(previous) or any(expected.get(key) != sha for key, sha in done.items()):
            raise ValueError("Existing results do not match the Oracle inputs")
        if any(row["result"]["status"] == "error" and
               (row["result"]["trace"].get("transport_error") or
                any(issue.startswith("Extraction failed: URLError")
                    for issue in row["result"]["verification"]["issues"]))
               for row in previous):
            raise ValueError("Existing results contain connection errors; start a new benchmark")
        cases = [row for row in cases if (row[0], row[1]["id"]) not in done]
    with output_path.open("a" if resume else "x", encoding="utf-8") as output:
        for dataset, case, request, gold in cases:
            started = perf_counter()
            result = generate_v2(request, endpoint=ENDPOINT, settings=SETTINGS)
            if result.trace.get("transport_error"):
                raise RuntimeError("Local LLM connection failed; resume once the server is available")
            visible = [result.summary.text, *(step.action for step in result.steps)]
            row = {
                "dataset": dataset, "id": case["id"], "split": case["split"],
                "answerable": case["answerable"], "model": models[0]["id"],
                "input_sha256": hashlib.sha256(request.model_dump_json().encode()).hexdigest(),
                "input": request.model_dump(), "gold": gold, "result": result.model_dump(),
                "lexical_hits": proxy_hits(gold, visible),
                "step_hits": proxy_hits(gold, [step.action for step in result.steps]),
                "seconds": round(perf_counter() - started, 3),
            }
            output.write(json.dumps(row, ensure_ascii=False) + "\n")
            output.flush()
            print(dataset, case["id"], result.status, row["seconds"], flush=True)


def summarize(rows):
    for dataset in ("complex50", "rag100"):
        for split in ("all", "dev", "test"):
            group = [r for r in rows if r["dataset"] == dataset and (split == "all" or r["split"] == split)]
            if len(group) < 2:
                continue
            statuses = Counter(r["result"]["status"] for r in group)
            seconds = [r["seconds"] for r in group]
            print(dataset, split, len(group), dict(statuses),
                  "matches", sum(len(r["lexical_hits"]) for r in group),
                  "/", sum(len(r["gold"]) for r in group),
                  "steps", sum(len(r["step_hits"]) for r in group),
                  "complete", sum(bool(r["gold"]) and len(r["lexical_hits"]) == len(r["gold"]) for r in group),
                  "p50 p95", round(median(seconds), 2), round(quantiles(seconds, n=20, method="inclusive")[-1], 2))


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--repair-from", type=Path)
    parser.add_argument("--retries", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.summary:
        rows = read_rows(args.output)
        expected = {(dataset, case["id"]) for dataset, case in load_cases()}
        assert len(rows) == 150 and {(r["dataset"], r["id"]) for r in rows} == expected
        summarize(rows)
        if args.retries:
            retried = read_rows(args.retries)
            by_id = {(r["dataset"], r["id"]): r for r in retried}
            errors = {(r["dataset"], r["id"]): r for r in rows if r["result"]["status"] == "error"}
            if set(by_id) != set(errors) or len(retried) != len(errors):
                raise ValueError("Retry trace must contain exactly the failed questions")
            for key, row in by_id.items():
                if row["input_sha256"] != errors[key]["input_sha256"]:
                    raise ValueError(f"Input differs for {key}")
            print("After targeted recovery:")
            summarize([by_id.get((r["dataset"], r["id"]), r) for r in rows])
    else:
        main(args.output, args.repair_from, resume=args.resume)
