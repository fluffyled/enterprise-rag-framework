import gc
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from navigator.backends import BGEM3Backend, E5SmallBackend, MiniLMRerankingBackend
from navigator.config import load_config
from navigator.retrieval import Retriever, build_index
from navigator.settings import ROOT


def release(model):
    del model
    gc.collect()
    torch.cuda.empty_cache()


def main():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA недоступна")
    result = {"gpu": torch.cuda.get_device_name(0), "vram_bytes": torch.cuda.get_device_properties(0).total_memory, "checks": {}}
    texts = ["Сотрудник подаёт заявку в течение пяти рабочих дней.", "Приказ утверждает руководитель подразделения."]

    started = time.perf_counter()
    e5 = E5SmallBackend(device="cuda")
    vectors = e5.encode_documents(texts)
    query = e5.encode_query("Когда подаётся заявка?")
    assert len(vectors) == 2 and len(query) == vectors.shape[1]
    result["checks"]["e5"] = {"device": str(e5.model.device), "shape": list(vectors.shape), "seconds": time.perf_counter() - started, "peak_vram_bytes": torch.cuda.max_memory_allocated()}
    release(e5)

    started = time.perf_counter()
    reranker = MiniLMRerankingBackend(device="cuda")
    scores = reranker.predict([("Когда подаётся заявка?", text) for text in texts])
    assert len(scores) == 2
    result["checks"]["reranker"] = {"device": str(reranker.model.device), "scores": [float(score) for score in scores], "seconds": time.perf_counter() - started, "peak_vram_bytes": torch.cuda.max_memory_allocated()}
    release(reranker)

    started = time.perf_counter()
    bge = BGEM3Backend("bge-m3-full", device="cuda")
    encoded = bge.encode_documents_full(texts)
    bundle = bge.encode_query_full("Когда подаётся заявка?")
    query_vectors = bundle["colbert_vecs"][0] if isinstance(bundle["colbert_vecs"], list) else bundle["colbert_vecs"]
    late_scores = bge.late_interaction_scores(query_vectors, [SimpleNamespace(content=text) for text in texts])
    assert len(encoded["dense_vecs"]) == 2 and len(encoded["lexical_weights"]) == 2
    assert bundle["dense_vecs"].shape[0] == 1 and len(bundle["lexical_weights"]) == 1
    assert len(late_scores) == 2
    result["checks"]["bge_m3"] = {"device": bge.device, "dense_shape": list(encoded["dense_vecs"].shape), "sparse_queries": len(bundle["lexical_weights"]), "late_interaction_scores": late_scores, "late_interaction_device": "cuda", "seconds": time.perf_counter() - started, "peak_vram_bytes": torch.cuda.max_memory_allocated()}
    release(bge)

    directory = ROOT / "data" / "cuda_smoke"
    chunks_path = directory / "chunks.json"
    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    chunks = []
    for index, text in enumerate(texts):
        chunks.append({"id": f"cuda-{index}", "content": text, "meta": {"name": f"synthetic-{index}", "document_id": f"synthetic-{index}", "relative_path": f"synthetic-{index}", "chunk_id": f"cuda-{index}", "locator": "synthetic", "source_span": {"document_id": f"synthetic-{index}", "start": 0, "end": len(text)}, "original_content": text}})
    chunks_path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    config = load_config(ROOT / "configs" / "retrieval_cuda_stable.yaml")
    build_index(config, chunks_path=chunks_path, index_path=directory / "index.json")
    retriever = Retriever(config=config, index_path=directory / "index.json")
    search = retriever.search("Когда подаётся заявка и кто утверждает приказ?")
    assert len(search) == 2 and all(document.meta.get("source_span") for document in search)
    result["checks"]["pipeline"] = {"device": config["retrieval"]["device"], "selected": len(search), "timings": search.timings, "source_spans_preserved": True}
    output = ROOT / "reports" / "retrieval_v3" / "cuda_smoke.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
