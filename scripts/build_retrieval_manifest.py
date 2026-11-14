"""Построение retrieval_manifest.json (этап 5 аудита v4.1)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from navigator.manifest import build_manifest

if __name__ == "__main__":
    manifest = build_manifest()
    print(sys.path.insert(0, "") or "")
    import json
    print(json.dumps({"git_sha": manifest["git_sha"], "configs": manifest["configs"], "document_count": manifest["corpus"]["document_count"]}, ensure_ascii=False, indent=2))
