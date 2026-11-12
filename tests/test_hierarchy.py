from docx import Document

from navigator.ingest import units
from navigator.structure import enrich_hierarchy, heading_from_text, profile_documents


def chunk(chunk_id, start, section="1. Общие положения"):
    return {"id": chunk_id, "content": f"text {chunk_id}", "meta": {"chunk_id": chunk_id, "document_id": "doc", "relative_path": "doc", "document_version_id": "version", "name": "Document", "section": section, "source_span": {"document_id": "doc", "start": start, "end": start + 5}}}


def test_stable_hierarchy_and_bidirectional_links():
    chunks = [chunk("b", 10), chunk("a", 0), chunk("c", 20, "2. Процедура")]
    nodes = enrich_hierarchy(chunks)
    assert chunks[0]["meta"]["previous"] == "a"
    assert chunks[1]["meta"]["next"] == "b"
    assert chunks[0]["meta"]["parent_id"] != chunks[2]["meta"]["parent_id"]
    documents = profile_documents(nodes, "document")
    sections = profile_documents(nodes, "section")
    assert len(documents) == 1 and len(sections) == 2
    assert len(documents[0]["meta"]["node_id"]) == 24
    assert enrich_hierarchy([dict(item, meta=dict(item["meta"])) for item in chunks])[0]["id"] == nodes[0]["id"]


def test_heading_detection_styles_numbering_and_fallback():
    assert heading_from_text("2.3. Порядок действий")["level"] == 2
    assert heading_from_text("Общие положения", "Heading 1")["level"] == 1
    assert heading_from_text("Раздел", numbering={"num_id": 4, "level": 1})["level"] == 2
    assert heading_from_text("Обычный текст без заголовка") is None


def test_docx_heading_style_and_numbering(tmp_path):
    document = Document()
    document.add_paragraph("Раздел", style="Heading 1")
    path = tmp_path / "heading.docx"
    document.save(path)
    text, meta = list(units(path))[0]
    assert text == "Раздел"
    assert meta["style"] == "Heading 1"
