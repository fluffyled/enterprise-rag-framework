import gzip
import json
import random

from huggingface_hub import HfApi

from .common import public_hf_file


def read_tsv(path):
    return [line.rstrip("\n").split("\t") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_miracl(split="dev", query_limit=None, corpus_limit=500, full_corpus=False, seed=42):
    language = "ru"
    prefix = "miracl-v1.0-ru"
    topic_path = public_hf_file("miracl/miracl", f"{prefix}/topics/topics.{prefix}-{split}.tsv")
    qrel_path = public_hf_file("miracl/miracl", f"{prefix}/qrels/qrels.{prefix}-{split}.tsv")
    topics = {row[0]: row[1] for row in read_tsv(topic_path)}
    relevance = {}
    for row in read_tsv(qrel_path):
        if len(row) >= 4:
            relevance.setdefault(row[0], {})[row[2]] = int(row[3])
    query_ids = sorted(query_id for query_id in topics if any(value > 0 for value in relevance.get(query_id, {}).values()))
    selected_relevance = {query_id: relevance[query_id] for query_id in query_ids}
    positive_ids = {document_id for values in selected_relevance.values() for document_id, value in values.items() if value > 0}
    files = sorted(HfApi().list_repo_files("miracl/miracl-corpus", repo_type="dataset"))
    shards = [name for name in files if name.startswith("miracl-corpus-v1.0-ru/docs-") and name.endswith(".jsonl.gz")]
    if not shards:
        raise RuntimeError("Не найдены шарды русского корпуса MIRACL")
    documents = []
    known = set()
    rng = random.Random(seed)
    if not full_corpus:
        path = public_hf_file("miracl/miracl-corpus", shards[0])
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle]
        available = {str(row["docid"]) for row in rows}
        query_ids = sorted(query_id for query_id in query_ids if {document_id for document_id, value in relevance[query_id].items() if value > 0}.issubset(available))
        if query_limit is not None:
            query_ids = query_ids[:query_limit]
        selected_relevance = {query_id: relevance[query_id] for query_id in query_ids}
        positive_ids = {document_id for values in selected_relevance.values() for document_id, value in values.items() if value > 0}
        selected_rows = [row for row in rows if str(row["docid"]) in positive_ids]
        remaining = [row for row in rows if str(row["docid"]) not in positive_ids]
        rng.shuffle(remaining)
        selected_rows.extend(remaining[:max(0, (corpus_limit or len(rows)) - len(selected_rows))])
        for row in selected_rows:
            document_id = str(row["docid"])
            text = (row.get("title", "") + "\n" + row.get("text", "")).strip()
            documents.append({"document_id": document_id, "title": row.get("title", ""), "text": text})
            known.add(document_id)
    else:
        for shard in shards:
            path = public_hf_file("miracl/miracl-corpus", shard)
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                for line in handle:
                    row = json.loads(line)
                    document_id = str(row["docid"])
                    text = (row.get("title", "") + "\n" + row.get("text", "")).strip()
                    documents.append({"document_id": document_id, "title": row.get("title", ""), "text": text})
                    known.add(document_id)
    missing = positive_ids - known
    if missing:
        raise RuntimeError(f"В загруженном корпусе отсутствуют {len(missing)} gold-документов")
    documents.sort(key=lambda row: row["document_id"])
    queries = [{
        "id": query_id,
        "question": topics[query_id],
        "answerable": True,
        "question_type": "wikipedia_retrieval",
        "gold_document_ids": sorted(document_id for document_id, value in selected_relevance[query_id].items() if value > 0),
        "graded_relevance": selected_relevance[query_id],
        "evidence_groups": [],
        "language": "ru",
    } for query_id in query_ids]
    return {
        "name": "miracl_ru",
        "language": "ru",
        "documents": documents,
        "queries": queries,
        "chunks": [{"id": row["document_id"], "content": row["text"], "meta": {"name": row["title"], "relative_path": row["document_id"], "document_id": row["document_id"], "chunk_id": row["document_id"], "locator": "passage", "source_span": {"document_id": row["document_id"], "start": 0, "end": len(row["text"])}, "original_content": row["text"]}} for row in documents],
        "metadata": {"official": bool(full_corpus and query_limit is None), "official_corpus": full_corpus, "pilot": not full_corpus, "incomplete_judgments": True, "seed": seed, "shards": shards if full_corpus else shards[:1]},
    }
