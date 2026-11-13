import json
import unicodedata
from pathlib import Path

from .common import chunks_from_documents, download_and_extract_zip


DATA_URL = "https://www.dropbox.com/scl/fo/r7xfa5i3hdsbxex1w6amw/AID389Olvtm-ZLTKAPrw6k4?rlkey=5n8zrbk4c08lbit3iiexofmwg&st=0hu354cq&dl=1"


def parse_legalbench(benchmark, corpus, benchmark_name="unknown", query_limit=None):
    tests = benchmark["tests"][:query_limit] if query_limit is not None else benchmark["tests"]
    queries = []
    required_documents = set()
    for index, test in enumerate(tests):
        alternatives_by_document = {}
        for snippet in test["snippets"]:
            document_id = snippet["file_path"]
            start, end = map(int, snippet["span"])
            alternatives_by_document.setdefault(document_id, []).append({"document_id": document_id, "start": start, "end": end})
            required_documents.add(document_id)
        groups = [{"id": f"snippet-{document_id}-{number}", "alternatives": [span]} for document_id, spans in alternatives_by_document.items() for number, span in enumerate(spans)]
        queries.append({
            "id": f"{benchmark_name}-{index}",
            "question": test["query"],
            "answerable": True,
            "question_type": "legal_precise_span",
            "gold_document_ids": sorted(alternatives_by_document),
            "evidence_groups": groups,
            "tags": test.get("tags", []),
        })
    documents = [{"document_id": path, "title": Path(path).name, "text": text} for path, text in sorted(corpus.items()) if path in required_documents]
    return {
        "name": "legalbench_rag",
        "language": "en",
        "documents": documents,
        "queries": queries,
        "chunks": chunks_from_documents(documents),
        "metadata": {"official": False, "benchmark_name": benchmark_name, "source_record_count": len(benchmark["tests"]), "selected_record_count": len(queries)},
    }


def load_legalbench(data_dir=None, benchmark_name="mini", query_limit=None):
    root = Path(data_dir) if data_dir else download_and_extract_zip(DATA_URL, "legalbench-rag")
    benchmark_root = root / "benchmarks"
    if benchmark_name == "mini":
        candidates = sorted(benchmark_root.glob("*mini*.json"))
        if not candidates:
            raise FileNotFoundError("LegalBench-RAG-mini не найден; укажите benchmark_name или скачайте официальный архив")
        benchmark_path = candidates[0]
    else:
        benchmark_path = benchmark_root / f"{benchmark_name.removesuffix('.json')}.json"
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    required = {snippet["file_path"] for test in benchmark["tests"] for snippet in test["snippets"]}
    corpus = {}
    for file_path in sorted(required):
        document_path = root / "corpus" / file_path
        if not document_path.exists():
            portable = "/".join("".join("_" if char in '<>:"|?*' else char for char in part) for part in Path(file_path).parts)
            document_path = root / "corpus" / portable
        if not document_path.exists():
            parent = document_path.parent
            normalized_name = unicodedata.normalize("NFC", document_path.name)
            matches = [candidate for candidate in parent.iterdir() if unicodedata.normalize("NFC", candidate.name) == normalized_name]
            if len(matches) != 1:
                raise FileNotFoundError(f"Не удалось однозначно найти документ: {file_path}")
            document_path = matches[0]
        corpus[file_path] = document_path.read_text(encoding="utf-8")
    return parse_legalbench(benchmark, corpus, benchmark_path.stem, query_limit)
