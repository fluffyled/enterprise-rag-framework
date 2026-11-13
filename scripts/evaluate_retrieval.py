import argparse
import json
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.config import config_fingerprint, default_config_path, load_config
from navigator.evaluation.benchmark import ResourceMonitor, load_internal_dataset, run_benchmark, save_benchmark
from navigator.evaluation.datasets.common import save_chunks
from navigator.retrieval import Retriever, build_index
from navigator.settings import DATA, INDEX, ROOT


def parse_args():
    parser = argparse.ArgumentParser(description="Retrieval-only benchmark без вызова LLM")
    parser.add_argument("--dataset", choices=["internal", "multidoc2dial", "legalbench", "miracl"], default="internal")
    parser.add_argument("--config", default=str(default_config_path()))
    parser.add_argument("--split", default=None)
    parser.add_argument("--name", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--document-limit", type=int, default=None)
    parser.add_argument("--corpus-limit", type=int, default=500)
    parser.add_argument("--shard-limit", type=int, default=1)
    parser.add_argument("--full-corpus", action="store_true")
    parser.add_argument("--legal-data-dir")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--cold", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--index-path", help="Переиспользовать совместимый индекс другого эксперимента")
    return parser.parse_args()


def load_dataset(args):
    split = args.split or ("all" if args.dataset == "internal" else "dev")
    if args.dataset == "internal":
        return load_internal_dataset(split)
    if args.dataset == "multidoc2dial":
        from navigator.evaluation.datasets import load_multidoc2dial
        return load_multidoc2dial(split=args.split or "validation", query_limit=args.limit, document_limit=args.document_limit)
    if args.dataset == "legalbench":
        from navigator.evaluation.datasets import load_legalbench
        return load_legalbench(args.legal_data_dir, benchmark_name=args.split or "mini", query_limit=args.limit)
    from navigator.evaluation.datasets import load_miracl
    return load_miracl(split=args.split or "dev", query_limit=args.limit, corpus_limit=args.corpus_limit, full_corpus=args.full_corpus, seed=42, shard_limit=args.shard_limit)


def main():
    args = parse_args()
    config = load_config(args.config)
    random.seed(config["seed"])
    np.random.seed(config["seed"])
    dataset = load_dataset(args)
    if args.limit is not None and args.dataset == "internal":
        dataset["queries"] = dataset["queries"][:args.limit]
    index_path = Path(args.index_path) if args.index_path else INDEX
    indexing = {}
    if not args.index_path and (args.dataset != "internal" or args.rebuild):
        fingerprint = config_fingerprint(config)
        directory = DATA / "experiment_indexes" / args.dataset / fingerprint[:16]
        chunks_path = DATA / "chunks.json" if args.dataset == "internal" else directory / "chunks.json"
        index_path = directory / "index.json"
        if args.dataset != "internal":
            save_chunks(dataset["chunks"], chunks_path)
        if args.rebuild or not index_path.exists():
            started = time.perf_counter()
            with ResourceMonitor() as resources:
                build_index(config, chunks_path=chunks_path, index_path=index_path)
            indexing = {"indexing": {"n": 1, "mean": time.perf_counter() - started}, "indexing_resources": resources.to_dict()}
    started = time.perf_counter()
    retriever = Retriever(config=config, index_path=index_path)
    initialization_seconds = time.perf_counter() - started
    result = run_benchmark(retriever, dataset, config=config, top_k=config["retrieval"]["output_top_k"], repeat=args.repeat, warm=not args.cold)
    result["latency"]["initialization"] = {"n": 1, "mean": initialization_seconds, "measurement_mode": "cold"}
    result["latency"].update(indexing)
    name = args.name or ("baseline" if args.dataset == "internal" else args.dataset)
    output = ROOT / "reports" / "retrieval_experiments" / name
    save_benchmark(result, output, config, index_path)
    print(json.dumps({"output": str(output), "metrics": result["metrics"], "errors": len(result["errors"])}, ensure_ascii=False, indent=2))
    if result["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
