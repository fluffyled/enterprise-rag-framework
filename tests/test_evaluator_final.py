"""Этап 4 аудита v4.1: дополнительные инварианты evaluator."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.evaluate_complex_rag import stage_coverage


def make_gold_row():
    return {
        "gold_evidence": [
            {
                "evidence_id": "DA_p1_1",
                "document_code": "DA",
                "document_filename": "doc_a.docx",
                "source_unit_id": "DA::docx_paragraph::1",
                "evidence_needle": "не более 16 рабочих часов",
                "evidence_quote": "время первичной обработки составляет не более 16 рабочих часов",
            }
        ],
        "required_facts": [{"fact_id": "F1", "text": "срок", "evidence_ids": ["DA_p1_1"]}],
    }


def test_incomplete_citation_is_not_strict():
    """Фрагмент цитаты без needle — максимум soft, не strict."""
    gold_row = make_gold_row()
    partial = [("c", "время первичной обработки составляет не более требований", "doc_a.docx")]
    result = stage_coverage(partial, gold_row, {})
    assert result["clause_recall_strict"] == 0.0


def test_repeated_evidence_does_not_inflate():
    """Дубликаты evidence с одним ID не увеличивают recall."""
    gold_row = make_gold_row()
    gold_row["gold_evidence"] = gold_row["gold_evidence"] * 3
    items = [("c", "время первичной обработки составляет не более 16 рабочих часов", "doc_a.docx")]
    result = stage_coverage(items, gold_row, {})
    assert result["clause_recall"] == 1.0  # не 3.0 — знаменатель по уникальным ID


def test_oracle_stage_is_maximal():
    gold_row = make_gold_row()
    items = [(e["evidence_id"], e["evidence_quote"], e["document_filename"]) for e in gold_row["gold_evidence"]]
    result = stage_coverage(items, gold_row, {})
    assert result["clause_recall"] == 1.0
    assert result["fact_coverage"] == 1.0
    assert result["all_evidence_found"] == 1.0


def test_metrics_semantics_documented():
    """Strict evidence recall — проверка текстового вхождения в ПРАВИЛЬНОМ
    документе; проверка точного clause ID не выполняется (зафиксировано)."""
    import scripts.evaluate_complex_rag as evaluator

    source = Path(evaluator.__file__).read_text(encoding="utf-8")
    assert "clause_recall_strict" in source
    assert "clause_recall_legacy" in source  # legacy только для исторического сравнения
