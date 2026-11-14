"""Application entry point for connected questions."""
import json
import os
from functools import lru_cache
from pathlib import Path
from threading import RLock
from time import perf_counter
from uuid import uuid4

import yaml

from .config import load_config
from .evidence_adapter import adapt_evidence
from .generation_service import AnswerResponse, GenerationService
from .settings import DATA, INDEX, ROOT

PROFILES = {"fast": ROOT / "configs/retrieval_bge_adaptive_rerank.yaml",
            "quality": ROOT / "configs/retrieval_h1_parent.yaml"}
GENERATION = ("legacy", "g2")
LOCK = RLock()


@lru_cache(maxsize=1)
def application_config():
    path = Path(os.environ.get("NAVIGATOR_APPLICATION_CONFIG", ROOT / "configs/application.yaml"))
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (not isinstance(config, dict) or set(config) != {"retrieval", "generation"}
            or config["retrieval"] not in PROFILES or config["generation"] not in GENERATION):
        raise ValueError("Некорректный профиль в application.yaml")
    for mode, path in PROFILES.items():
        settings = load_config(path)["retrieval"]
        if (settings["embedding_backend"] != "bge-m3-sparse"
                or settings["reranker_backend"] != "bge-reranker-v2-m3"
                or not settings["rerank"] or settings["parent_expansion"] != (mode == "quality")):
            raise ValueError(f"Некорректная конфигурация retrieval: {mode}")
    return config


@lru_cache(maxsize=1)
def resources(index, clauses, corpus, manifest, stamps):
    from .parent_expansion import load_clause_store
    from .retrieval import Retriever

    store = load_clause_store(clauses) if clauses.exists() else {}
    sources = json.loads(corpus.read_text(encoding="utf-8")) if corpus.exists() else []
    retriever = Retriever(config=PROFILES["fast"], index_path=index,
                          clause_store_path=clauses, manifest_path=manifest)
    retriever._clause_store = store
    return retriever, store, sources


def clear_resources():
    global _resource_key
    resources.cache_clear()
    _resource_key = None


def index_path(snapshot=None):
    return Path(snapshot) / "index.json" if snapshot else INDEX


def ask(question, retrieval=None, generation=None, *, snapshot=None, diagnostics=False):
    info = {}
    phase = "Конфигурация"
    try:
        config = application_config()
        retrieval = retrieval or config["retrieval"]
        generation = generation or config["generation"]
        if retrieval not in PROFILES or generation not in GENERATION:
            raise ValueError("Неизвестный режим приложения")
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 6000:
            raise ValueError("Введите вопрос длиной от 1 до 6000 символов.")
        phase = "Retrieval"
        index = index_path(snapshot)
        manifest = Path(snapshot) / "snapshot.json" if snapshot else None
        if manifest and manifest.exists() and json.loads(manifest.read_text(encoding="utf-8"))["empty"]:
            return AnswerResponse("insufficient", missing_requirements=["Корпус документов пуст."])
        if not index.exists():
            return AnswerResponse("error", error="Retrieval: индекс отсутствует. Постройте базу документов.")
        corpus = Path(snapshot) / "source_documents.json" if snapshot else DATA / "source_documents.json"
        clauses = Path(snapshot) / "clauses.json" if snapshot else DATA / "clauses/clauses.json"
        if retrieval == "quality" and not clauses.exists():
            raise ValueError("Для Quality требуется Clause Store. Перестройте базу документов.")
        with LOCK:
            started = perf_counter()
            paths = [index, clauses, corpus, *PROFILES.values()] + ([manifest] if manifest else [])
            stamps = tuple(path.stat().st_mtime_ns if path.exists() else None for path in paths)
            # Evict before loading a new index to avoid concurrent copies of GPU models.
            global _resource_key
            if _resource_key != (index, stamps):
                resources.cache_clear()
                _resource_key = index, stamps
            retriever, store, sources = resources(index, clauses, corpus, manifest, stamps)
            documents = retriever.search(question.strip(), config=load_config(PROFILES[retrieval]))
            evidence = adapt_evidence(documents, retrieval, sources, store, add_parents=generation == "g2")
            info.update(retrieval_ms=round((perf_counter() - started) * 1000), retrieval=retrieval,
                        generation=generation, retrieval_details=getattr(documents, "metadata", {}),
                        evidence_ids=[item.id for item in evidence])
            phase = "LLM"
            started = perf_counter()
            response = GenerationService().generate(question.strip(), evidence, generation)
            info["generation_ms"] = round((perf_counter() - started) * 1000)
        trace = response.diagnostics.pop("trace", None)
        if trace:
            model = next((call.get("model") for call in trace["calls"] if call.get("model")), None)
            if model:
                info["model"] = model.replace("\\", "/").rsplit("/", 1)[-1]
        if diagnostics and trace:
            target = DATA / "traces" / (uuid4().hex + ".json")
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps({**info, "trace": trace}, ensure_ascii=False), encoding="utf-8")
                info["trace_file"] = target.name
            except OSError:
                response.warnings.append("Диагностическая трасса недоступна для записи.")
        response.diagnostics.update(info)
        return response
    except KeyboardInterrupt:
        return AnswerResponse("error", error="Запрос отменён.", diagnostics=info)
    except Exception as exc:
        return AnswerResponse("error", error=f"{phase}: {exc}", diagnostics=info)


_resource_key = None
