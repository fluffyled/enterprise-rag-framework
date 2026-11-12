import hashlib
import json
import re
from collections import defaultdict


HEADING_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(\S.*)$")


def heading_from_text(text, style=None, numbering=None):
    style = style or ""
    style_match = re.match(r"(?:Heading|Заголовок)\s*(\d+)", style, flags=re.IGNORECASE)
    first_line = text.strip().splitlines()[0].strip() if text.strip() else ""
    match = HEADING_PATTERN.match(first_line)
    if match:
        number, title = match.groups()
        return {"number": number, "level": number.count(".") + 1, "title": first_line[:240]}
    if style_match or style.lower() == "title":
        level = int(style_match.group(1)) if style_match else 1
        return {"number": None, "level": level, "title": first_line[:240]}
    if numbering:
        return {"number": str(numbering.get("num_id")), "level": int(numbering.get("level", 0)) + 1, "title": first_line[:240]}
    return None


def stable_node_id(version_id, node_type, locator):
    payload = json.dumps([version_id, node_type, locator], ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def enrich_hierarchy(chunks):
    grouped = defaultdict(list)
    for chunk in chunks:
        meta = chunk["meta"]
        document_id = meta.get("document_id") or meta["relative_path"]
        grouped[document_id].append(chunk)
    nodes = []
    for document_id, document_chunks in grouped.items():
        document_chunks.sort(key=lambda chunk: (chunk["meta"].get("source_span") or {}).get("start", chunk["meta"].get("word_start", 0)))
        version = document_chunks[0]["meta"].get("document_version_id") or document_chunks[0]["meta"].get("sha256") or document_id
        document_node_id = stable_node_id(version, "document", document_id)
        section_groups = defaultdict(list)
        previous = None
        for chunk in document_chunks:
            meta = chunk["meta"]
            section_title = meta.get("section") or meta.get("sheet") or "Без явного раздела"
            section_id = stable_node_id(version, "section", section_title)
            chunk_id = meta.get("chunk_id") or chunk["id"]
            meta.update({"document_node_id": document_node_id, "section_id": section_id, "node_id": stable_node_id(version, "chunk", chunk_id), "parent_id": section_id, "previous": previous, "next": None})
            if previous:
                by_previous = next(item for item in document_chunks if (item["meta"].get("chunk_id") or item["id"]) == previous)
                by_previous["meta"]["next"] = chunk_id
            previous = chunk_id
            section_groups[section_title].append(chunk)
        section_ids = []
        for section_title, section_chunks in section_groups.items():
            section_id = stable_node_id(version, "section", section_title)
            section_ids.append(section_id)
            children = [chunk["meta"]["chunk_id"] for chunk in section_chunks]
            text = "\n".join(chunk["content"] for chunk in section_chunks)
            nodes.append({"id": section_id, "type": "section", "document_id": document_id, "title": section_title, "content": text[:12000], "parent": document_node_id, "children": children, "previous": None, "next": None})
        title = document_chunks[0]["meta"].get("name") or document_id
        profile = title + "\n" + "\n".join(section_groups)
        nodes.append({"id": document_node_id, "type": "document", "document_id": document_id, "title": title, "content": profile, "parent": None, "children": section_ids, "previous": None, "next": None})
        for chunk in document_chunks:
            nodes.append({"id": chunk["meta"]["node_id"], "source_id": chunk["meta"]["chunk_id"], "type": "chunk", "document_id": document_id, "title": chunk["meta"].get("section"), "content": chunk["content"], "parent": chunk["meta"]["parent_id"], "children": [], "previous": chunk["meta"]["previous"], "next": chunk["meta"]["next"]})
    return nodes


def profile_documents(nodes, level):
    profiles = []
    for node in nodes:
        if node["type"] != level:
            continue
        document_id = node["document_id"]
        profile_id = f"{level}:{node['id']}"
        profiles.append({
            "id": profile_id,
            "content": node["content"],
            "meta": {"name": node["title"], "relative_path": document_id, "document_id": document_id, "node_id": node["id"], "section_id": node["id"] if level == "section" else None, "profile_type": level, "original_content": node["content"]},
        })
    return profiles
