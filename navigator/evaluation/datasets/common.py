import hashlib
import json
import re
import urllib.request
import zipfile
from pathlib import Path

from huggingface_hub import hf_hub_download

from ...settings import ROOT


def cache_directory(name):
    path = ROOT / ".cache" / "retrieval_datasets" / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def download(url, destination):
    destination = Path(destination)
    if not destination.exists():
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        with urllib.request.urlopen(url, timeout=180) as response, temporary.open("wb") as output:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
        temporary.replace(destination)
    return destination


def download_and_extract_zip(url, name):
    directory = cache_directory(name)
    archive = download(url, directory / "dataset.zip")
    marker = directory / ".extracted"
    if not marker.exists():
        with zipfile.ZipFile(archive) as extracted:
            for member in extracted.infolist():
                if member.is_dir():
                    continue
                target = (directory / member.filename).resolve()
                if directory.resolve() not in target.parents:
                    raise ValueError("Небезопасный путь в ZIP")
            extracted.extractall(directory)
        marker.write_text("ok\n", encoding="utf-8")
    return directory


def public_hf_file(repository, filename):
    return Path(hf_hub_download(repo_id=repository, repo_type="dataset", filename=filename))


def chunk_document(document, chunk_words=110, chunk_stride=90):
    text = document["text"]
    words = list(re.finditer(r"\S+", text))
    chunks = []
    for word_start in range(0, len(words), chunk_stride):
        selected = words[word_start:word_start + chunk_words]
        if not selected:
            continue
        start, end = selected[0].start(), selected[-1].end()
        content = text[start:end]
        chunk_id = hashlib.sha256(json.dumps([document["document_id"], start, end], ensure_ascii=False).encode("utf-8")).hexdigest()[:24]
        chunks.append({
            "id": chunk_id,
            "content": content,
            "meta": {
                "name": document.get("title") or document["document_id"],
                "relative_path": document["document_id"],
                "document_id": document["document_id"],
                "chunk_id": chunk_id,
                "section_id": document.get("section_id"),
                "section": document.get("section") or document.get("title"),
                "locator": f"chars {start}-{end}",
                "source_span": {"document_id": document["document_id"], "start": start, "end": end},
                "original_content": content,
                "word_start": word_start,
            },
        })
    return chunks


def chunks_from_documents(documents, chunk_words=110, chunk_stride=90):
    return [chunk for document in documents for chunk in chunk_document(document, chunk_words, chunk_stride)]


def save_chunks(chunks, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    return path
