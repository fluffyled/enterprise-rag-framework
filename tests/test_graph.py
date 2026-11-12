from navigator.graph import build_document_graph, expand_documents


def chunk(document_id, text, sha):
    return {"id": sha, "content": text, "meta": {"document_id": document_id, "relative_path": document_id, "document_version_id": sha, "name": document_id, "locator": "synthetic", "source_span": {"document_id": document_id, "start": 0, "end": len(text)}}}


def test_confirmed_repeal_relation_and_graph_expansion():
    graph = build_document_graph([
        chunk("Приказ N 2 от 02.01.2024.docx", "Считать утратившим силу приказ от 01.01.2023 № 1.", "new"),
        chunk("Приказ N 1 от 01.01.2023.docx", "Старый порядок.", "old"),
    ])
    repeals = [edge for edge in graph["edges"] if edge["relation"] == "repeals"]
    assert len(repeals) == 1
    assert repeals[0]["status"] == "confirmed_textual_reference"
    assert repeals[0]["evidence_span"]["locator"] == "synthetic"
    related = expand_documents(graph, ["Приказ N 2 от 02.01.2024.docx"], depth=1, relation_mode="amendments")
    assert list(related) == ["Приказ N 1 от 01.01.2023.docx"]
    assert not expand_documents(graph, ["Приказ N 2 от 02.01.2024.docx"], depth=1, relation_mode="references")


def test_ambiguous_reference_is_not_resolved():
    graph = build_document_graph([
        chunk("Приказ N 2.docx", "Ссылаемся на приказ № 1.", "new"),
        chunk("Приказ N 1 от 01.01.2023.docx", "Первая версия.", "old1"),
        chunk("Приказ N 1 от 01.01.2024.docx", "Вторая версия.", "old2"),
    ])
    assert graph["statistics"]["unresolved_reference_candidates"] == 1
    assert not graph["edges"]
