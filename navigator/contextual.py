def build_contextual_representation(chunk, hierarchy):
    meta = chunk["meta"]
    original = meta.get("original_content", chunk["content"])
    parts = [meta.get("name") or meta.get("document_id") or ""]
    section = meta.get("section") or meta.get("sheet")
    if section:
        parts.append(str(section))
    heading = meta.get("heading") or {}
    if heading.get("title") and heading["title"] != section:
        parts.append(heading["title"])
    mode = hierarchy.get("contextual_mode", "headers")
    if mode in ("parent", "description"):
        section_id = meta.get("section_id")
        section_node = hierarchy.get("sections", {}).get(section_id)
        if section_node:
            parent_text = section_node["content"].replace(original, " ").strip()
            if parent_text:
                parts.append("Контекст пункта: " + parent_text[:600])
    if mode == "description":
        previous_id = meta.get("previous")
        previous = hierarchy.get("chunks", {}).get(previous_id)
        if previous:
            parts.append("Предыдущий пункт: " + previous[:240])
    parts.append(original)
    return "\n".join(part for part in parts if part)


def hierarchy_lookup(nodes):
    sections = {node["id"]: node for node in nodes if node["type"] == "section"}
    by_chunk_id = {}
    for node in nodes:
        if node["type"] == "chunk":
            by_chunk_id[node["source_id"]] = node["content"]
    return {"sections": sections, "chunks": by_chunk_id}


def prepare_contextual_chunks(chunks, nodes, config):
    if not config["retrieval"]["contextual"]:
        return chunks
    lookup = hierarchy_lookup(nodes)
    lookup["contextual_mode"] = config["retrieval"]["contextual_mode"]
    limit = config["retrieval"]["contextual_max_chars"]
    for chunk in chunks:
        original = chunk["content"]
        chunk["meta"]["original_content"] = original
        search_content = build_contextual_representation(chunk, lookup)[:limit]
        chunk["meta"]["search_content"] = search_content
        chunk["content"] = search_content
    return chunks
