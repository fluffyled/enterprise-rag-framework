from types import SimpleNamespace
import pytest
from navigator.answer import validate, answer
from navigator.ingest import units

# Synthetic unit fixtures exercise validators, not the hackathon evaluation corpus.
def doc(text): return SimpleNamespace(content=text, meta={"name": "unit fixture", "locator": "unit"})

def test_quote_preserved():
    text = "Срок обработки заявки составляет один рабочий день."
    r = validate({"insufficient": False, "answer": [{"source": 1, "quote": text}]}, [doc(text)])
    assert r["status"] == "supported_quotes"

@pytest.mark.parametrize("item", [{"source": 2, "quote": "Придуманная дословная цитата"}, {"source": 1, "quote": "Неподтверждённое утверждение"}, {"source": True, "quote": "Срок обработки заявки составляет один рабочий день."}])
def test_rejects_invalid_quote(item):
    with pytest.raises(ValueError): validate({"insufficient": False, "answer": [item]}, [doc("Срок обработки заявки составляет один рабочий день.")])

def test_insufficient_does_not_leak_answer():
    r = validate({"insufficient": True, "answer": [{"source": 1, "quote": "Не следует выводить"}]}, [])
    assert not r["answer"] and r["status"] == "insufficient"

def test_external_endpoint_blocked():
    with pytest.raises(ValueError): answer("question", [], "https://external.example/v1/chat/completions")

def test_docx_block_order(tmp_path):
    from docx import Document
    d = Document(); d.add_paragraph("Перед таблицей"); d.add_table(rows=1, cols=1).cell(0, 0).text = "Внутри таблицы"; d.add_paragraph("После таблицы")
    f = tmp_path / "fixture.docx"; d.save(f)
    assert [t for t, _ in units(f)] == ["Перед таблицей", "Внутри таблицы", "После таблицы"]

def test_excel_cell_coordinates_and_formula(tmp_path):
    from openpyxl import Workbook
    d = Workbook(); d.active["A3"] = "Показатель"; d.active["B3"] = "=1+1"; d.active.merge_cells("A1:B1")
    f = tmp_path / "fixture.xlsx"; d.save(f)
    text, meta = list(units(f))[0]
    assert "A3: Показатель" in text and "формула =1+1" in text and "не вычислено" in text
    assert meta["locator"].endswith("строка 3")


def test_real_corpus_ids_and_file_coverage():
    import json
    from navigator.settings import DATA
    file = DATA / "chunks.json"
    if not file.exists(): pytest.skip("Real private corpus is not distributed")
    chunks = json.loads(file.read_text(encoding="utf-8"))
    assert len(chunks) == len({d["id"] for d in chunks})
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    assert not manifest["errors"]
    assert {d["meta"]["relative_path"] for d in chunks} == {d["relative_path"] for d in manifest["files"]}


def test_sentence_selection_only_returns_source_text():
    from navigator.answer import sentence_options, selected_quotes
    docs = [doc("Ответ занимает один рабочий день. Следующий этап выполняет руководитель.")]
    options = sentence_options(docs)
    result = selected_quotes({"answer_ids": [1], "step_ids": [], "conflict_pairs": [], "insufficient": False}, options, docs)
    assert result["answer"][0]["quote"] == "Ответ занимает один рабочий день."
    with pytest.raises(ValueError):
        selected_quotes({"answer_ids": [999], "insufficient": False}, options, docs)
