import re
from collections import defaultdict

from .resolver import document_signature, resolve_reference
from .schema import Edge, Node, serialize_graph


def build_document_graph(chunks):
    grouped = defaultdict(list)
    for chunk in chunks:
        grouped[chunk["meta"].get("document_id") or chunk["meta"]["relative_path"]].append(chunk)
    catalog = {}
    nodes = []
    for document_id, document_chunks in grouped.items():
        text = "\n".join(chunk["content"] for chunk in document_chunks)
        signature = document_signature({"document_id": document_id, "text": text})
        version = document_chunks[0]["meta"].get("document_version_id") or document_chunks[0]["meta"].get("sha256")
        nodes.append(Node(f"document:{document_id}", "document", document_id, document_chunks[0]["meta"].get("name", document_id), version))
        nodes.append(Node(f"version:{version}", "document_version", document_id, document_id, version))
        if signature["number"]:
            catalog.setdefault(signature["number"], []).append({"document_id": document_id, **signature})
    edges = []
    unresolved = []
    seen = set()
    for document_id, document_chunks in grouped.items():
        for chunk in document_chunks:
            text = chunk["content"]
            for match in re.finditer(r"(?:приказ[а-я]*|распоряжени[а-я]*)[^\n]{0,100}?(?:от\s+(\d{2}\.\d{2}\.\d{4}))?[^\n]{0,30}?[№N]\s*(\d+(?:-\d+)?)", text, flags=re.IGNORECASE):
                reference = {"date": match.group(1), "number": match.group(2)}
                target = resolve_reference(reference, catalog)
                evidence = match.group(0)
                if not target:
                    unresolved.append({"source_id": document_id, "reference": reference, "evidence": evidence, "locator": chunk["meta"].get("locator")})
                    continue
                target_id = target["document_id"]
                if target_id == document_id:
                    continue
                prefix = text[max(0, match.start() - 100):match.start()].lower()
                relation = "references"
                if re.search(r"отмен|утратившим|прекрати", prefix + evidence.lower()):
                    relation = "repeals"
                elif "изменени" in (prefix + evidence.lower()):
                    relation = "amends"
                key = (document_id, target_id, relation, evidence)
                if key in seen:
                    continue
                seen.add(key)
                edges.append(Edge(f"document:{document_id}", f"document:{target_id}", relation, evidence, {"chunk_id": chunk["id"], "locator": chunk["meta"].get("locator"), "source_span": chunk["meta"].get("source_span")}, constraints={"date": reference["date"], "note": "textual relation; legal validity not asserted"}))
            for match in re.finditer(r"Приложени[ея][^\n]{0,30}?№?\s*(\d+[а-я]?)", text, flags=re.IGNORECASE):
                attachment_id = f"attachment:{document_id}:{match.group(1)}"
                if not any(node.id == attachment_id for node in nodes):
                    nodes.append(Node(attachment_id, "attachment", document_id, match.group(0), locator=chunk["meta"].get("locator")))
                key = (document_id, attachment_id, "contains", match.group(0))
                if key not in seen:
                    seen.add(key)
                    edges.append(Edge(f"document:{document_id}", attachment_id, "contains", match.group(0), {"chunk_id": chunk["id"], "locator": chunk["meta"].get("locator"), "source_span": chunk["meta"].get("source_span")}))
    payload = serialize_graph(nodes, edges)
    payload["unresolved_references"] = unresolved
    payload["statistics"] = {"documents": len(grouped), "edges_total": len(edges), "confirmed_document_edges": sum(edge.target_id.startswith("document:") for edge in edges), "unresolved_reference_candidates": len(unresolved)}
    return payload
