"""Run paired generation strategies on Oracle or frozen retrieval results."""
import argparse
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from time import perf_counter
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, build_opener
from zipfile import ZipFile

from answering.core import NoRedirect, check_endpoint
from answering.research import MODES, generate_answer
from answering.v2 import AnswerInputV1, generate_v2
from scripts.evaluate_generation_v2 import oracle_input
from haystack import Document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["dev", "test"], default="dev")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--case", action="append", help="Select a case within the given split")
    parser.add_argument("--fixed", type=Path, help="JSONL with id and input (AnswerInputV1)")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8091/v1/chat/completions")
    parser.add_argument("--modes", nargs="+", choices=["G0", "G0-H5", *MODES, "G2-no-retry"],
                        default=["G0", "G0-H5", *MODES])
    args = parser.parse_args()
    check_endpoint(args.endpoint)
    parsed = urlsplit(args.endpoint)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(f"{parsed.scheme}://{parsed.netloc}/v1/models", timeout=10) as response:
        models = json.load(response)["data"]
    if len(models) != 1 or "qwen3.5-4b-q4_k_m" not in models[0]["id"].casefold():
        parser.error("Only the local Qwen3.5-4B-Q4_K_M is allowed")
    with ZipFile(args.dataset) as archive:
        cases = [json.loads(line) for line in archive.read("hierarchical_complex_qa_50.jsonl").splitlines()]
    cases = [case for case in cases if case["split"] == args.split
             and (not args.case or case["id"] in args.case)][:args.limit]
    if not cases:
        parser.error("No cases match the requested split and IDs")
    frozen = {}
    if args.fixed:
        for line in args.fixed.read_text(encoding="utf-8-sig").splitlines():
            row = json.loads(line)
            if row["id"] in frozen:
                parser.error("Duplicate frozen case")
            frozen[row["id"]] = AnswerInputV1.model_validate(row["input"])
    requests = [(case, frozen[case["id"]] if args.fixed else oracle_input(case)) for case in cases]
    if any(request.question != case["question"].strip() for case, request in requests):
        parser.error("Frozen question differs from dataset")
    with args.output.open("x", encoding="utf-8") as stream:
        for case, request in requests:
            documents = [Document(id=e.id, content=e.full_text, meta={
                "document_id": e.document_id, "name": e.document_title or e.document_id,
                "locator": e.locator, "page": e.metadata.get("page"),
            }) for e in request.evidence]
            for mode in args.modes:
                started = perf_counter()
                if mode.startswith("G0"):
                    result = generate_answer(request.question, documents, args.endpoint, mode)
                else:
                    settings = replace(MODES["G2"], technical_retries=0) if mode == "G2-no-retry" else MODES[mode]
                    result = generate_v2(request, endpoint=args.endpoint, settings=settings).model_dump()
                row = {
                    "id": case["id"], "split": args.split, "mode": mode,
                    "context": str(args.fixed) if args.fixed else "Oracle",
                    "input": request.model_dump(),
                    "input_sha256": hashlib.sha256(request.model_dump_json().encode()).hexdigest(),
                    "gold": case["required_facts"], "model": models[0],
                    "seconds": round(perf_counter() - started, 3), "result": result,
                }
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                print(case["id"], mode, result["status"], row["seconds"], flush=True)


if __name__ == "__main__":
    main()
