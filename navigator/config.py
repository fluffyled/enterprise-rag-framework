import copy
import hashlib
import json
from pathlib import Path

import yaml

from .settings import ROOT


DEFAULT_CONFIG = {
    "schema_version": 1,
    "retrieval": {
        "hierarchical": False,
        "hierarchy_mode": "off",
        "contextual": False,
        "contextual_mode": "off",
        "coverage_aware": False,
        "selection_strategy": "top_k",
        "decomposition_method": "existing",
        "adaptive": False,
        "adaptive_mode": "off",
        "graph_expansion": False,
        "graph_depth": 1,
        "graph_relation_mode": "references",
        "embedding_backend": "e5-small",
        "reranker_backend": "mminilm",
        "device": "cpu",
        "candidate_top_k": 20,
        "output_top_k": 6,
        "context_token_budget": 2000,
        "rerank": True,
        "batch_cross_encoder": False,
        "chunk_words": 110,
        "chunk_stride": 90,
        "contextual_max_chars": 1200,
        "mmr_lambda": 0.7,
        "coverage_lambda": 0.15,
        "coverage_cost_normalization": True,
        "coverage_document_diversity": 0.0,
        "coverage_min_subtask": False,
        "protected_top_p": 2,
        "coverage_alpha": 0.5,
        "coverage_beta": 0.3,
        "coverage_gamma": 0.2,
        "adaptive_min_candidates": 4,
        "adaptive_min_unique_documents": 2,
        "adaptive_min_score": -4.0,
        "adaptive_max_expansions": 2,
        "bge_sparse_weight": 0.5,
        "bge_late_interaction_top_n": 20,
        "bge_fusion": "late_only",
        "bge_late_weight": 0.5,
    },
    "seed": 42,
}


def load_config(config=None):
    if config is None:
        result = copy.deepcopy(DEFAULT_CONFIG)
    elif isinstance(config, (str, Path)):
        with Path(config).open(encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
        result = merge_config(DEFAULT_CONFIG, loaded)
    elif isinstance(config, dict):
        result = merge_config(DEFAULT_CONFIG, config)
    else:
        raise TypeError("config должен быть dict, путём к YAML или None")
    retrieval = result["retrieval"]
    if retrieval["candidate_top_k"] < 1 or retrieval["output_top_k"] < 1:
        raise ValueError("top_k должен быть положительным")
    if retrieval["chunk_words"] < 1 or retrieval["chunk_stride"] < 1:
        raise ValueError("Параметры chunking должны быть положительными")
    if retrieval["chunk_stride"] > retrieval["chunk_words"]:
        raise ValueError("chunk_stride не может превышать chunk_words")
    if not 0 <= retrieval["mmr_lambda"] <= 1:
        raise ValueError("mmr_lambda должен быть в [0, 1]")
    return result


def merge_config(base, override):
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_config(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def config_fingerprint(config):
    normalized = load_config(config)
    payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def default_config_path():
    return ROOT / "configs" / "retrieval_baseline.yaml"
