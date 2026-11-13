"""Оценка вариантов retrieval на датасете rag_eval_dataset_100 (data/rag100).

Чанки внутреннего индекса привязываются к юнитам датасета (Dxx + page/paragraph)
по текстовому совпадению: для PDF — по meta.page, для DOCX — по вхождению
нормализованного текста абзаца в нормализованный текст чанка (нумерация абзацев
у нас и у датасета различается, поэтому привязка только текстовая).

Для каждой конфигурации пишутся два набора предсказаний:
- *_candidates.jsonl — reranked top-10 (ранжирующая способность пайплайна);
- *_selected.jsonl — итоговый контекст top-6 (что реально получает LLM).
Метрики считает data/rag100/evaluate_retrieval.py (их скрипт, без изменений).
Дополнительно считаем needle Recall по итоговому контексту.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from navigator.config import load_config
from navigator.retrieval import Retriever

RAG = ROOT / "data" / "rag100"
INDEX = ROOT / "data" / "index.json"
OUT = ROOT / "reports" / "retrieval_experiments" / "rag100"

CONFIGS = {
    "B0_baseline": {"config": "configs/retrieval_cuda_baseline.yaml"},
    "V2_stable": {"config": "configs/retrieval_cuda_stable.yaml"},
    "V2_mmr": {"config": "configs/retrieval_cuda_mmr.yaml"},
    "V3F_final": {"config": "configs/retrieval_v3_final.yaml"},
    "BGE_e2": {"config": "configs/retrieval_cuda_bge_e2.yaml", "index": "data/experiment_indexes/internal/f08c5dd40c32277b/index.json"},
}

ABZ_RE = re.compile(r"^\u0430\u0431\u0437\u0430\u0446 (\d+)")


def norm(text):
    return re.sub(r"\s+", " ", text or " ").strip()


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_chunk_unit_map(index_path=None):
    manifest = {m["name"]: m["id"] for m in json.loads((RAG / "documents_manifest.json").read_text(encoding="utf-8"))}
    filename_to_did = manifest
    units = load_jsonl(RAG / "corpus_units.jsonl")
    index = json.loads(Path(index_path).read_text(encoding="utf-8") if index_path else INDEX.read_text(encoding="utf-8"))
    chunks = index["documents"]

    units_by_doc = {}
    for unit in units:
        if len(norm(unit["text"])) < 10:
            continue
        units_by_doc.setdefault(unit["document_id"], []).append(unit)

    chunk_units = {}
    docx_text_stats = {"linked": 0, "orphan": 0}
    for chunk in chunks:
        meta = chunk["meta"]
        did = manifest.get(meta["name"])
        if not did:
            continue
        found = []
        if meta["name"].lower().endswith(".pdf"):
            page = meta.get("page")
            if page and str(page).isdigit():
                found.append({"document_id": did, "unit_type": "page", "unit_locator": int(page)})
        else:
            match = ABZ_RE.match(meta.get("locator") or "")
            content_norm = norm(chunk["content"])
            if match and content_norm:
                for unit in units_by_doc.get(did, []):
                    if unit["unit_type"] == "paragraph" and norm(unit["text"]) in content_norm:
                        found.append({"document_id": did, "unit_type": "paragraph", "unit_locator": unit["unit_locator"]})
                if found:
                    docx_text_stats["linked"] += 1
                else:
                    docx_text_stats["orphan"] += 1
        if found:
            chunk_units[meta["chunk_id"]] = found

    gold = load_jsonl(RAG / "rag_gold_qa.jsonl")
    unit_keys = {(u["document_id"], u["unit_type"], u["unit_locator"]) for u in units}
    covered = set()
    for cid, units_found in chunk_units.items():
        for u in units_found:
            key = (u["document_id"], u["unit_type"], u["unit_locator"])
            if key in unit_keys:
                covered.add(key)
    gold_keys = set()
    for g in gold:
        if not g["answerable"]:
            continue
        loc = g["gold_location"]
        gold_keys.add((g["gold_document_id"], "page" if loc["type"] == "pdf_page" else "paragraph", loc.get("page") or loc.get("paragraph")))
    covered_gold = gold_keys & covered
    return chunk_units, filename_to_did, {
        "chunks_mapped": len(chunk_units),
        "docx": docx_text_stats,
        "gold_units": len(gold_keys),
        "gold_units_covered_by_chunks": len(covered_gold),
        "gold_units_missed": sorted(f"{k[0]}:{k[1]}:{k[2]}" for k in gold_keys - covered),
    }


def flatten(chunks_in_order, chunk_units):
    seen = set()
    retrieved = []
    for chunk_id in chunks_in_order:
        for unit in chunk_units.get(chunk_id, []):
            key = (unit["document_id"], unit["unit_type"], unit["unit_locator"])
            if key not in seen:
                seen.add(key)
                retrieved.append(unit)
    return retrieved


def run_config(name, config_path, gold, chunk_units, filename_to_did, index_path=None):
    import time

    config = load_config(ROOT / config_path)
    retriever = Retriever(config=config, index_path=index_path)
    candidate_rows, selected_rows = [], []
    needle_stats = {"hit": 0, "total": 0, "docs_hit6": 0}
    timings = []
    for g in gold:
        started = time.perf_counter()
        search = retriever.search(g["question"], config=config)
        timings.append(time.perf_counter() - started)
        trace = search.to_dict()
        cand_ids = [item["meta"].get("chunk_id") for item in trace["stages"].get("cross_encoder", [])][:10]
        sel_ids = [item["meta"].get("chunk_id") for item in trace["results"]]
        candidate_rows.append({"id": g["id"], "retrieved": flatten(cand_ids, chunk_units), "abstained": False})
        selected_rows.append({"id": g["id"], "retrieved": flatten(sel_ids, chunk_units), "abstained": False})
        if g["answerable"]:
            needle_stats["total"] += 1
            needle = g["evidence_needle"]
            if any(needle in item.content for item in search):
                needle_stats["hit"] += 1
            gold_docs = set(g["gold_document_ids"])
            if any(filename_to_did.get(item.meta.get("document_id")) in gold_docs for item in search):
                needle_stats["docs_hit6"] += 1
    del retriever
    ordered = sorted(timings)
    latency = {
        "n": len(timings),
        "median": ordered[len(ordered) // 2],
        "p95": ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))],
        "mean": sum(timings) / len(timings),
    }
    return candidate_rows, selected_rows, needle_stats, latency


def evaluate(predictions, split):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"_{predictions['name']}_{split}.jsonl"
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in predictions["rows"]), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(RAG / "evaluate_retrieval.py"), str(RAG / "rag_gold_qa.jsonl"), str(path), "--split", split],
        capture_output=True, text=True, encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr)
    return json.loads(proc.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--configs", default=None, help="comma-separated имена из CONFIGS")
    parser.add_argument("--split", default=None, help="test|dev|None(все)")
    parser.add_argument("--summary", default=str(OUT / "rag100_summary.json"))
    args = parser.parse_args()

    names = args.configs.split(",") if args.configs else list(CONFIGS)
    spec = CONFIGS[names[0]]
    index_path = ROOT / spec["index"] if spec.get("index") else None
    gold = load_jsonl(RAG / "rag_gold_qa.jsonl")
    chunk_units, filename_to_did, coverage = build_chunk_unit_map(index_path)
    print("mapping:", json.dumps(coverage, ensure_ascii=False))

    splits = [args.split] if args.split else ["test", "dev"]
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))["summary"]
    else:
        summary = {}
    for name in names:
        spec = CONFIGS[name]
        index_path = ROOT / spec["index"] if spec.get("index") else None
        candidate_rows, selected_rows, needle, latency = run_config(name, spec["config"], gold, chunk_units, filename_to_did, index_path)
        print(f"{name}: needle Recall@selected = {needle['hit']}/{needle['total']}, doc hit@6 = {needle['docs_hit6']}/{needle['total']}, median = {latency['median']:.3f}s")
        entry = {"needle_selected": needle, "latency": latency, "config": spec["config"]}
        for split in splits:
            gold_split = {g["id"] for g in gold if g["split"] == split}
            for kind, rows in (("candidates", candidate_rows), ("selected", selected_rows)):
                filtered = [row for row in rows if row["id"] in gold_split]
                metrics = evaluate({"name": f"{name}_{kind}", "rows": filtered}, split)
                entry[f"{split}_{kind}"] = metrics
        summary[name] = entry
        import subprocess
        env = {
            "git_sha": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip(),
            "models_lock": json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8")),
        }
        summary_path.write_text(json.dumps({"environment": env, "coverage": coverage, "summary": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(summary_path)


if __name__ == "__main__":
    main()
