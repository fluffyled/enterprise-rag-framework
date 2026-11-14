"""Paired generator runs on fixed evidence, without retrieval."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from time import perf_counter
from zipfile import ZipFile

from answering.contracts import Fragment
from answering.core import generate
from answering.v2 import AnswerInputV1, generate_v2
from answering.v2.pipeline import Settings


def oracle_input(case):
    evidence = []
    for row in case["gold_evidence"]:
        location = row["location"]
        start, end = location.get("start"), location.get("end")
        evidence.append({
            "id": row["evidence_id"],
            "document_id": row["document_code"],
            "document_title": row["document_filename"],
            "full_text": row["evidence_quote"],
            "locator": str(location.get("section") or location.get("page") or ""),
            "source_spans": [[start, end]] if isinstance(start, int) and isinstance(end, int) and end > start else [],
            "metadata": {"source_unit_id": row.get("source_unit_id"),
                         "source_text_sha256": row.get("source_text_sha256")},
        })
    return AnswerInputV1(question=case["question"], evidence=evidence)


def words(text):
    return set(re.findall(r"\w+", text.casefold()))


def proxy_hits(required, texts):
    candidates = [words(text) for text in texts]
    hits = []
    for fact in required:
        target = words(fact["text"])
        if target and any(len(candidate & target) / len(target) >= 0.70 for candidate in candidates):
            hits.append(fact["fact_id"])
    return hits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("hierarchical_rag_plan_and_dataset_50.zip"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8091/v1/chat/completions")
    parser.add_argument("--model", default="Qwen3.5-4B-Q4_K_M")
    parser.add_argument("--split", choices=["dev", "test", "all"], default="dev")
    parser.add_argument("--limit", type=int, help="Optional cap on the number of questions")
    parser.add_argument("--context", choices=["Q0", "H1", "Oracle", "H4"], default="Oracle")
    parser.add_argument("--fixed-inputs", type=Path, help="JSONL with id and input (AnswerInputV1)")
    parser.add_argument("--arms", nargs="+", help="Defaults to all arms for the selected context")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    prefix = {"Q0": "A", "H1": "B", "Oracle": "C", "H4": "D"}[args.context]
    available = [prefix + n for n in (("1", "2") if prefix == "D" else ("0", "1", "2"))]
    arms = args.arms or available
    if set(arms) - {*available, prefix + "1-global"}:
        parser.error("Arms must match the selected context")
    if args.context != "Oracle" and not args.fixed_inputs:
        parser.error("Saved evidence is required for this context")
    fixed = {}
    if args.fixed_inputs:
        for line in args.fixed_inputs.read_text(encoding="utf-8-sig").splitlines():
            row = json.loads(line)
            if row["id"] in fixed:
                parser.error("Duplicate fixed case ID")
            fixed[row["id"]] = AnswerInputV1.model_validate(row["input"])
    with ZipFile(args.dataset) as archive:
        cases = [json.loads(row) for row in archive.read("hierarchical_complex_qa_50.jsonl").splitlines()]
    cases = [case for case in cases if (args.split == "all" or case["split"] == args.split)
             and (not args.fixed_inputs or case["id"] in fixed)][:args.limit]
    if not cases:
        parser.error("No cases in selected split")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        for case in cases:
            request = fixed[case["id"]] if args.fixed_inputs else oracle_input(case)
            if request.question != case["question"].strip():
                raise ValueError(f"Question mismatch for {case['id']}")
            for arm in arms:
                started = perf_counter()
                if arm.endswith("0"):
                    fragments = [Fragment(e.id, e.document_id, e.full_text, e.document_title or e.document_id, e.locator or "—")
                                 for e in request.evidence]
                    trace = {}
                    result = generate(request.question, fragments, endpoint=args.endpoint, trace=trace)
                    result["trace"] = trace
                    texts = [row["quote"] for row in result["steps"]]
                else:
                    result = generate_v2(request, endpoint=args.endpoint, settings=Settings(
                        verify=arm.endswith("2"), extraction="global" if arm.endswith("-global") else "map",
                    )).model_dump()
                    texts = [row["action"] for row in result["steps"]]
                row = {
                    "id": case["id"], "split": case["split"], "answerable": case["answerable"],
                    "arm": arm, "model": args.model, "context": args.context,
                    "input_sha256": hashlib.sha256(request.model_dump_json().encode()).hexdigest(),
                    "seconds": round(perf_counter() - started, 3), "input": request.model_dump(),
                    "gold": case["required_facts"], "result": result,
                    "step_fact_hits_lexical_proxy": proxy_hits(case["required_facts"], texts),
                }
                if not arm.endswith("0"):
                    extracted = result["trace"].get("extracted_facts", [])
                    row["extracted_fact_hits_lexical_proxy"] = proxy_hits(case["required_facts"], [f["text"] for f in extracted])
                output.write(json.dumps(row, ensure_ascii=False) + "\n")
                output.flush()
                print(case["id"], arm, result["status"], row["seconds"], flush=True)


if __name__ == "__main__":
    main()
