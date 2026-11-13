import hashlib
import json
import os
import platform
import statistics
import subprocess
import threading
import time
import traceback
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import numpy as np
import psutil

from ..config import load_config
from ..settings import ROOT
from .metrics import aggregate_metrics, latency_metrics, per_query_metrics


class ResourceMonitor:
    def __init__(self):
        self.process = psutil.Process(os.getpid())
        self.initial_rss = self.process.memory_info().rss
        self.peak_rss = self.initial_rss
        self.peak_vram = 0
        self.running = False
        self.thread = None

    def _sample(self):
        while self.running:
            self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)
            try:
                import torch
                if torch.cuda.is_available():
                    self.peak_vram = max(self.peak_vram, torch.cuda.max_memory_allocated())
            except (ImportError, RuntimeError):
                pass
            time.sleep(0.05)

    def __enter__(self):
        self.running = True
        self.thread = threading.Thread(target=self._sample, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.running = False
        self.thread.join()
        self._sample_once()

    def _sample_once(self):
        self.peak_rss = max(self.peak_rss, self.process.memory_info().rss)

    def to_dict(self):
        return {"peak_rss_bytes": self.peak_rss, "rss_growth_bytes": self.peak_rss - self.initial_rss, "peak_vram_bytes": self.peak_vram, "sampler_interval_seconds": 0.05}


def environment_metadata(config, index_fingerprint=None):
    try:
        git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        git_sha = "unknown"
    try:
        git_dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    except (subprocess.SubprocessError, FileNotFoundError):
        git_dirty = None
    packages = {}
    for package in ("haystack-ai", "sentence-transformers", "transformers", "torch", "numpy"):
        try:
            packages[package] = version(package)
        except Exception:
            packages[package] = "unknown"
    models = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    return {
        "git_sha": git_sha,
        "git_dirty": git_dirty,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "seed": config.get("seed", 42),
        "hardware": {"platform": platform.platform(), "python": platform.python_version(), "processor": platform.processor(), "logical_cpus": os.cpu_count(), "ram_bytes": psutil.virtual_memory().total},
        "packages": packages,
        "models": models,
        "index_fingerprint": index_fingerprint,
        "config": config,
    }


def load_internal_dataset(split="all"):
    path = ROOT / "data" / f"retrieval_eval_{split}.json"
    if not path.exists() and split == "all":
        path = ROOT / "data" / "eval_cases.json"
    if not path.exists():
        raise FileNotFoundError(f"Нет файла разметки: {path}")
    rows = json.loads(path.read_text(encoding="utf-8"))
    queries = rows.get("queries", rows) if isinstance(rows, dict) else rows
    return {"name": "internal", "language": "ru", "queries": queries, "metadata": {"private": True, "split": split}}


def _convert_legacy_case(case):
    converted = dict(case)
    if "gold_document_ids" not in converted:
        converted["gold_document_ids"] = converted.get("expected_docs", [])
    converted.setdefault("answerable", not converted.get("must_abstain", False))
    converted.setdefault("question_type", converted.get("id", "unknown"))
    converted.setdefault("evidence_groups", converted.get("evidence_groups", []))
    return converted


def run_benchmark(retriever, dataset, config=None, top_k=6, repeat=1, warm=True):
    config = load_config(config)
    query_material = json.dumps([{"id": case["id"], "question": case["question"], "gold_document_ids": case.get("gold_document_ids"), "evidence_groups": case.get("evidence_groups"), "graded_relevance": case.get("graded_relevance")} for case in dataset["queries"]], ensure_ascii=False, sort_keys=True).encode("utf-8")
    dataset.setdefault("metadata", {})["query_set_sha256"] = hashlib.sha256(query_material).hexdigest()
    rows = []
    errors = []
    with ResourceMonitor() as resources:
        for case in dataset["queries"]:
            case = _convert_legacy_case(case)
            try:
                observations = []
                for iteration in range(repeat):
                    if not warm and iteration:
                        raise ValueError("Для cold замеров создавайте отдельный Retriever на каждый запуск")
                    result = retriever.search(case["question"], top_k=top_k, config=config)
                    observations.append(result.timings)
                    if iteration == 0:
                        candidates = result.stages.get("cross_encoder", result.to_dict()["results"])
                        metrics = per_query_metrics(candidates, case, list(result))
                        trace = result.to_dict()
                        graph = trace["metadata"].get("graph")
                        if graph:
                            related = set(graph["related_documents"])
                            gold = set(case.get("gold_document_ids", []))
                            metrics["graph_added_documents"] = len(related)
                            metrics["graph_irrelevant_added"] = len(related - gold)
                row = {"id": case["id"], "question_type": case.get("question_type"), "answerable": case.get("answerable"), "gold_document_ids": case.get("gold_document_ids", []), "metrics": metrics, "trace": trace, "repeat_timings": observations, "measurement_mode": "warm" if warm else "cold", "adaptive": trace["metadata"].get("adaptive")}
                rows.append(row)
            except Exception as error:
                errors.append({"id": case.get("id"), "type": type(error).__name__, "error": str(error), "traceback": traceback.format_exc()})
    per_query = [row["metrics"] for row in rows]
    stage_timings = {}
    for stage in ("embedding", "bm25", "bge_sparse", "dense", "rrf", "hierarchical_retrieval", "parent_expansion", "query_analysis", "subtask_retrieval", "graph_expansion", "adaptive_retrieval", "late_interaction", "reranking", "context_selection", "total"):
        stage_timings[stage] = latency_metrics([timing[stage] for row in rows for timing in row["repeat_timings"] if stage in timing])
    aggregate = aggregate_metrics(per_query)
    adaptive_rows = [row for row in rows if row.get("adaptive")]
    if adaptive_rows:
        aggregate["adaptive_expansion_rate"] = sum(row["adaptive"]["expanded"] for row in adaptive_rows) / len(adaptive_rows)
        false_sufficiency = [row for row in adaptive_rows if row["adaptive"]["initial"]["sufficient"] and row["metrics"].get("all_evidence_hit@6") == 0]
        aggregate["false_sufficiency_count"] = len(false_sufficiency)
        aggregate["false_sufficiency_rate"] = len(false_sufficiency) / len(adaptive_rows)
    return {
        "metrics": aggregate,
        "per_query": rows,
        "errors": errors,
        "latency": stage_timings,
        "resources": resources.to_dict(),
        "dataset": {"name": dataset["name"], "language": dataset.get("language"), "metadata": dataset.get("metadata", {}), "questions": len(dataset["queries"]), "evaluated": len(rows)},
    }


def save_benchmark(result, output_dir, config, index_path=None):
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    index_path = Path(index_path) if index_path else None
    index_fingerprint = None
    if index_path and index_path.exists():
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        index_fingerprint = payload.get("index_fingerprint", "legacy")
        result["index_bytes"] = index_path.stat().st_size
    metadata = environment_metadata(config, index_fingerprint)
    result["run"] = metadata
    (output / "config.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "metrics.json").write_text(json.dumps({"metrics": result["metrics"], "dataset": result["dataset"], "resources": result["resources"], "index_bytes": result.get("index_bytes")}, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "per_query_results.json").write_text(json.dumps(result["per_query"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "latency.json").write_text(json.dumps(result["latency"], ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Retrieval experiment", "", f"Questions: {result['dataset']['evaluated']}/{result['dataset']['questions']}", "", "| Metric | Value |", "|---|---:|"]
    lines.extend(f"| {key} | {value:.6f} |" if isinstance(value, float) else f"| {key} | {value} |" for key, value in result["metrics"].items() if not key.endswith("_n"))
    (output / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    error_lines = ["# Errors", ""]
    error_lines.extend(f"- {error['id']}: {error['type']}: {error['error']}" for error in result["errors"])
    evidence_errors = [row for row in result["per_query"] if row["metrics"].get("all_evidence_hit@6") == 0]
    error_lines.extend(["", f"## Evidence errors: {len(evidence_errors)}", ""])
    for row in evidence_errors:
        candidate_documents = {item.get("document_id") for item in row["trace"]["stages"].get("cross_encoder", [])}
        gold_documents = set(row.get("gold_document_ids", []))
        error_lines.append(f"- {row['id']}; type={row.get('question_type')}; correct_document_candidate={bool(gold_documents & candidate_documents) if gold_documents else 'not_applicable'}")
    (output / "errors.md").write_text("\n".join(error_lines) + "\n", encoding="utf-8")
    return output
