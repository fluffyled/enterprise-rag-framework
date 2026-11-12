from collections import deque


def expand_documents(graph, seed_document_ids, depth=1, relation_mode="references"):
    allowed = {"references", "contains", "supplements"} if relation_mode == "references" else set()
    if relation_mode == "amendments":
        allowed = {"references", "amends", "repeals", "supersedes", "contains", "supplements"}
    adjacency = {}
    for edge in graph["edges"]:
        if edge["status"] != "confirmed_textual_reference" or edge["relation"] not in allowed:
            continue
        source = edge["source_id"].removeprefix("document:")
        target = edge["target_id"].removeprefix("document:")
        if target.startswith("attachment:"):
            continue
        adjacency.setdefault(source, []).append((target, edge))
        adjacency.setdefault(target, []).append((source, edge))
    found = {}
    queue = deque((document_id, 0) for document_id in seed_document_ids)
    seen = set(seed_document_ids)
    while queue:
        current, current_depth = queue.popleft()
        if current_depth >= depth:
            continue
        for target, edge in adjacency.get(current, []):
            found.setdefault(target, {"depth": current_depth + 1, "evidence": []})["evidence"].append(edge)
            if target not in seen:
                seen.add(target)
                queue.append((target, current_depth + 1))
    for seed in seed_document_ids:
        found.pop(seed, None)
    return found
