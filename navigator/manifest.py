"""Валидация совместимости артефактов retrieval (этап 5 аудита v4.1).

retrieval_manifest.json фиксирует: коммит, корпус, parser/chunking версии,
checksum Clause Store и индексов, hash конфигураций, версии моделей, seed,
fingerprint evaluation-датасета. При несовместимости — понятная ошибка
(или требование пересборки), а не поиск по несогласованным артефактам.
"""

import hashlib
import json
import subprocess
from pathlib import Path

from .settings import ROOT

MANIFEST_PATH = ROOT / "data/retrieval_manifest.json"

STABLE_CONFIGS = ("retrieval_fast_stable.yaml", "retrieval_quality_stable.yaml", "retrieval_stable.yaml")


def _sha256_file(path, chunk_size=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT).stdout.strip()
    except Exception:
        return None


def build_manifest(output_path=None):
    source_documents = ROOT / "data/source_documents.json"
    clauses = ROOT / "data/clauses/clauses.json"
    import importlib.metadata as md

    configs = {}
    for name in STABLE_CONFIGS:
        path = ROOT / "configs" / name
        if path.exists():
            configs[name] = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    lock = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    manifest = {
        "name": "retrieval-v4.1",
        "git_sha": _git_sha(),
        "seed": 42,
        "corpus": {
            "source_documents_sha256": _sha256_file(source_documents),
            "document_count": len(json.loads(source_documents.read_text(encoding="utf-8"))),
        },
        "parser": {
            "clause_store_sha256": _sha256_file(clauses) if clauses.exists() else None,
            "clause_build_report": "data/clauses/clause_build_report.json",
        },
        "indexes": {
            "bge_internal": {
                "path": "data/experiment_indexes/internal/f08c5dd40c32277b/index.json",
                "sha256": _sha256_file(ROOT / "data/experiment_indexes/internal/f08c5dd40c32277b/index.json"),
            }
        },
        "configs": configs,
        "models": {role: lock[role]["revision"][:8] for role in ("embedding", "reranker", "bge_m3", "reranker_bge_v2_m3", "llm") if role in lock},
        "libraries": {
            "torch": md.version("torch"),
            "sentence-transformers": md.version("sentence-transformers"),
            "haystack-ai": md.version("haystack-ai"),
        },
        "evaluation": {
            "complex50_sha256": _sha256_file(ROOT / "data/hrag50/hierarchical_complex_qa_50.jsonl") if (ROOT / "data/hrag50/hierarchical_complex_qa_50.jsonl").exists() else None,
            "rag100_sha256": _sha256_file(ROOT / "data/rag100/rag_gold_qa.jsonl") if (ROOT / "data/rag100/rag_gold_qa.jsonl").exists() else None,
        },
    }
    out = Path(output_path) if output_path else MANIFEST_PATH
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def validate(config_path=None, index_path=None, strict=True, *, manifest_path=None, require_manifest=False):
    """Проверка совместимости. strict=False — только предупреждения (возвращает
    список строк); strict=True — RuntimeError при критической рассинхронизации."""
    if manifest_path is not None:
        manifest_path = Path(manifest_path)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for name in ("index.json", "clauses.json", "source_documents.json"):
            if _sha256_file(manifest_path.parent / name) != manifest[name]:
                raise RuntimeError(f"Артефакт корпуса изменился: {name}")
        return []
    if not MANIFEST_PATH.exists():
        if require_manifest:
            raise RuntimeError("Отсутствует манифест корпуса. Постройте базу документов.")
        return ["manifest отсутствует — валидация пропущена (scripts/build_retrieval_manifest.py)"]
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    problems = []
    if config_path:
        path = Path(config_path)
        if path.exists() and path.name in manifest["configs"]:
            current = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
            if current != manifest["configs"][path.name]:
                problems.append(f"конфиг {path.name} изменился с момента фиксации manifest")
    if index_path:
        index_info = manifest["indexes"]["bge_internal"]
        candidate = Path(index_path)
        if candidate.exists() and (ROOT / index_info["path"]).exists() and candidate.samefile(ROOT / index_info["path"]):
            if _sha256_file(candidate) != index_info["sha256"]:
                problems.append("BGE-индекс изменился: пересоберите индекс или manifest")
        elif require_manifest:
            problems.append("Индекс отсутствует в манифесте. Постройте снимок корпуса.")
    clauses = ROOT / "data/clauses/clauses.json"
    if clauses.exists() and manifest["parser"]["clause_store_sha256"]:
        if _sha256_file(clauses) != manifest["parser"]["clause_store_sha256"]:
            problems.append("Clause Store изменился: пересоберите store или manifest")
    if require_manifest and not manifest["parser"].get("clause_store_sha256"):
        problems.append("В манифесте отсутствует контрольная сумма Clause Store.")
    corpus = ROOT / "data/source_documents.json"
    if require_manifest and (not corpus.exists() or not clauses.exists()):
        problems.append("Отсутствуют исходные тексты или Clause Store.")
    if corpus.exists() and _sha256_file(corpus) != manifest["corpus"]["source_documents_sha256"]:
        problems.append("Корпус документов изменился: требуется полная пересборка")
    if strict and problems:
        raise RuntimeError("Retrieval manifest: несовместимость артефактов:\n- " + "\n- ".join(problems))
    return problems
