"""Emit reproducibility metadata without including any corpus contents."""
import argparse
import json
import subprocess
from pathlib import Path

from navigator.corpus import fingerprint
from navigator.rag_service import PROFILES, application_config
from navigator.settings import ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    model_lock = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    answer_lock = json.loads((ROOT / "answer-model.lock.json").read_text(encoding="utf-8"))
    manifest = {
        "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "application": application_config(),
        "models": {role: model_lock[role] for role in ("bge_m3", "reranker_bge_v2_m3")} | {"llm": answer_lock},
        "profiles_sha256": {name: fingerprint(path) for name, path in PROFILES.items()},
        "index_sha256": fingerprint(args.index),
    }
    args.output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
