"""Publish complete corpus snapshots for the local Streamlit workspace."""
import hashlib
import json
import shutil
from pathlib import Path
from uuid import uuid4

from .settings import DATA


def fingerprint(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def rebuild(directory, uploads=(), *, raw=DATA / "raw"):
    from .ingest import ingest
    from .retrieval import build_index
    from scripts.build_clause_store import parse_clauses

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = directory / uuid4().hex
    pending = snapshot / "raw"
    pending.mkdir(parents=True)
    try:
        if raw.exists():
            shutil.copytree(raw, pending, dirs_exist_ok=True)
        for name, path in uploads:
            # Source identity survives rebuilds and includes its display name.
            target = pending / ".uploads" / path.stem / Path(name).name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        manifest = {"empty": not any(path.is_file() for path in pending.rglob("*"))}
        if not manifest["empty"]:
            ingest(raw=pending, output=snapshot)
            documents = json.loads((snapshot / "source_documents.json").read_text(encoding="utf-8"))
            entries = {}
            seen = set()
            for document in documents:
                sha = document["sha256"]
                if sha in seen:
                    # The frozen Clause Store lookup is SHA-based. Keep both chunks.
                    entries.pop(sha, None)
                    continue
                seen.add(sha)
                doc_id = document["document_id"]
                entries[sha] = {"document_id": doc_id, "clauses": parse_clauses(doc_id, sha, document["text"])}
            (snapshot / "clauses.json").write_text(json.dumps({"documents": entries}, ensure_ascii=False), encoding="utf-8")
            from .rag_service import LOCK, PROFILES, clear_resources
            with LOCK:
                clear_resources()
                build_index(config=PROFILES["fast"], chunks_path=snapshot / "chunks.json",
                            index_path=snapshot / "index.json")
            manifest.update({name: fingerprint(snapshot / name)
                             for name in ("index.json", "clauses.json", "source_documents.json")})
        shutil.rmtree(pending)
        (snapshot / "snapshot.json").write_text(json.dumps(manifest), encoding="utf-8")
    except BaseException:
        shutil.rmtree(snapshot)
        raise
    return snapshot
