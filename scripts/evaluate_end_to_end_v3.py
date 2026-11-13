import argparse
import gc
import hashlib
import json
import sys
import time
from pathlib import Path

from haystack import Document

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.answer import PROMPT, answer
from navigator.config import load_config
from navigator.evaluation.alignment import group_coverage, normalize_evidence_groups
from navigator.evaluation.benchmark import ResourceMonitor, environment_metadata, load_internal_dataset
from navigator.evaluation.end_to_end import aggregate_answer_metrics, evaluate_answer, failure_category
from navigator.evaluation.metrics import latency_metrics
from navigator.retrieval import Retriever
from navigator.settings import ROOT


def oracle_documents(case):
    documents = []
    for group in normalize_evidence_groups(case):
        if not group["alternatives"]:
            continue
        gold = max(group["alternatives"], key=lambda span: len(span.text or ""))
        documents.append(Document(content=gold.text or "", meta={"document_id": gold.document_id, "name": gold.document_id, "chunk_id": f"oracle-{group['id']}"}))
    return documents


def all_groups_covered(results, case):
    groups = normalize_evidence_groups(case)
    return bool(groups) and all(any(group_coverage([result], group) > 0 for result in results) for group in groups)


def run_experiment(name, config_path, cases, endpoint, output_root):
    oracle = config_path == "oracle"
    config = load_config(None if oracle else config_path)
    retriever = None if oracle else Retriever(config=config)
    rows = []
    output = output_root / name
    output.mkdir(parents=True, exist_ok=True)
    with ResourceMonitor() as resources:
        for case in cases:
            started = time.perf_counter()
            retrieval_seconds = 0.0
            trace = None
            if oracle:
                documents = oracle_documents(case)
                candidate_all = context_all = bool(case.get("evidence_groups"))
            else:
                retrieval_started = time.perf_counter()
                search = retriever.search(case["question"], config=config)
                retrieval_seconds = time.perf_counter() - retrieval_started
                documents = list(search)
                trace = search.to_dict()
                candidates = trace["stages"].get("cross_encoder", [])
                candidate_all = all_groups_covered(candidates, case)
                context_all = all_groups_covered(trace["results"], case)
            generation_started = time.perf_counter()
            result = answer(case["question"], documents, endpoint=endpoint)
            generation_seconds = time.perf_counter() - generation_started
            answer_metrics = evaluate_answer(result, case)
            row = {
                "id": case["id"],
                "question": case["question"],
                "question_type": case.get("question_type"),
                "answerable": case.get("answerable", True),
                "result": result,
                "answer_metrics": answer_metrics,
                "failure_category": failure_category(result, answer_metrics, candidate_all, context_all, case.get("answerable", True)) if not answer_metrics["answer_correctness_proxy"] else None,
                "candidate_all_evidence": candidate_all,
                "context_all_evidence": context_all,
                "retrieval_seconds": retrieval_seconds,
                "generation_seconds": generation_seconds,
                "total_seconds": time.perf_counter() - started,
                "sources": [{"chunk_id": document.meta.get("chunk_id"), "document_id": document.meta.get("document_id"), "content": document.content} for document in documents],
                "retrieval_trace": trace,
                "oracle_context": oracle,
            }
            rows.append(row)
            (output / "per_query_results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
            print(name, case["id"], result["status"], round(row["total_seconds"], 3), flush=True)
    metrics = aggregate_answer_metrics(rows)
    latency = {
        "retrieval": latency_metrics([row["retrieval_seconds"] for row in rows]),
        "generation": latency_metrics([row["generation_seconds"] for row in rows]),
        "total": latency_metrics([row["total_seconds"] for row in rows]),
    }
    failures = {}
    for row in rows:
        if row["failure_category"]:
            failures[row["failure_category"]] = failures.get(row["failure_category"], 0) + 1
    metadata = environment_metadata(config)
    metadata.update({"experiment": name, "oracle_context": oracle, "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(), "answer_module_sha256": hashlib.sha256((ROOT / "navigator" / "answer.py").read_bytes()).hexdigest(), "llm_endpoint": endpoint})
    (output / "config.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps({"metrics": metrics, "failure_categories": failures, "resources": resources.to_dict()}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "latency.json").write_text(json.dumps(latency, ensure_ascii=False, indent=2), encoding="utf-8")
    del retriever
    gc.collect()
    return {"name": name, "metrics": metrics, "failure_categories": failures, "latency": latency, "resources": resources.to_dict(), "errors": sum(row["result"]["status"] == "error" for row in rows)}


def main():
    parser = argparse.ArgumentParser(description="End-to-end retrieval comparison с неизменной локальной Qwen")
    parser.add_argument("--split", default="test")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--experiment", action="append", help="name=config.yaml или name=oracle")
    parser.add_argument("--only-unanswerable", action="store_true")
    args = parser.parse_args()
    experiments = args.experiment or ["B0=configs/retrieval_baseline.yaml", "V2=configs/retrieval_stable.yaml"]
    cases = load_internal_dataset(args.split)["queries"]
    if args.only_unanswerable:
        cases = [case for case in cases if not case.get("answerable", True)]
    output_root = ROOT / "reports" / "retrieval_v3" / "end_to_end" / (args.split + ("_abstention" if args.only_unanswerable else ""))
    comparison = []
    for experiment in experiments:
        name, config_path = experiment.split("=", 1)
        comparison.append(run_experiment(name, config_path, cases, args.endpoint, output_root))
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "comparison.json").write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    if sum(row["errors"] for row in comparison):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
