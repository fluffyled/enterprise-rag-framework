"""Аудит: тесты, демонстрирующие прежнее завышение метрик complex50.

D2: совпадение needle в ДРУГОМ документе раньше засчитывалось как покрытие
(в корпусе есть дубликаты положений D05/D14).
D4: Step Recall раньше оценивался по ПОЛНЫМ цитатным блокам H5 — блок целиком
содержит evidence, поэтому метрика завышалась независимо от содержания шага.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.evaluate_complex_rag import generation_metrics, norm, quote_covers_fact, stage_coverage, step_text_covers_fact


def make_gold_row():
    return {
        "gold_evidence": [
            {
                "evidence_id": "DOCA_p1_1",
                "document_code": "DA",
                "document_filename": "doc_a.docx",
                "source_unit_id": "DA::docx_paragraph::1",
                "evidence_needle": "не более 16 рабочих часов",
                "evidence_quote": "время первичной обработки составляет не более 16 рабочих часов",
            }
        ],
        "required_facts": [
            {"fact_id": "F1", "text": "срок обработки", "evidence_ids": ["DOCA_p1_1"]}
        ],
    }


def test_cross_document_needle_match_is_not_coverage():
    """D2: тот же текст в чужом документе — НЕ покрытие (прежний код засчитывал)."""
    gold_row = make_gold_row()
    items_foreign = [("chunk_x", "…не более 16 рабочих часов…", "doc_b.docx")]
    items_own = [("chunk_y", "…не более 16 рабочих часов…", "doc_a.docx")]
    foreign = stage_coverage(items_foreign, gold_row, {})
    own = stage_coverage(items_own, gold_row, {})
    assert foreign["clause_recall"] == 0.0, "чужой документ не должен покрывать"
    assert foreign["clause_recall_legacy"] == 1.0, "legacy завышал: засчитывал чужой документ"
    assert own["clause_recall"] == 1.0


def test_strict_and_soft_reported_separately():
    gold_row = make_gold_row()
    soft_only = [("c", "время первичной обработки составляет не более требований для обращений", "doc_a.docx")]
    result = stage_coverage(soft_only, gold_row, {})
    assert result["clause_recall_strict"] == 0.0
    assert result["clause_recall"] == 1.0  # soft засчитан
    assert result["clause_recall_soft_only"] == 1.0


def test_step_recall_not_inflated_by_full_block_quote():
    """D4: шаг с посторонним действием, цитирующий блок целиком: прежняя
    оценка по цитате засчитала бы факт, новая — нет."""
    gold_row = make_gold_row()
    block_text = "4.2. Время первичной обработки и информирование пользователей: не более 16 рабочих часов."
    result = {
        "status": "supported_quotes",
        "answer": [{"quote": block_text, "action": "Оплатить счёт в бухгалтерии"}],
        "steps": [{"quote": block_text, "action": "Оплатить счёт в бухгалтерии"}],
    }
    metrics = generation_metrics(result, gold_row)
    assert metrics["legacy_step_recall"] == 1.0, "прежняя метрика завышена цитатой блока"
    assert metrics["step_recall"] == 0.0, "содержание шага не подтверждает факт"
    assert metrics["unsupported_quote_rate"] == 1.0


def test_step_recall_counts_supported_action():
    gold_row = make_gold_row()
    result = {
        "status": "supported_quotes",
        "answer": [],
        "steps": [{"quote": "заглушка", "action": "Первичная обработка занимает не более 16 рабочих часов", "actor": "", "condition": "", "deadline": "16 рабочих часов"}],
    }
    metrics = generation_metrics(result, gold_row)
    assert metrics["step_recall"] == 1.0


def test_error_separated_from_abstention():
    gold_row = make_gold_row()
    error = generation_metrics({"status": "error", "answer": [], "steps": []}, gold_row)
    abstain = generation_metrics({"status": "insufficient", "answer": [], "steps": []}, gold_row)
    assert error["error_rate"] == 1.0 and error["false_abstention"] == 0.0
    assert abstain["error_rate"] == 0.0 and abstain["false_abstention"] == 1.0


def test_composite_fact_requires_all_evidence():
    gold_row = make_gold_row()
    gold_row["gold_evidence"].append({
        "evidence_id": "DOCA_p2_2",
        "document_code": "DA",
        "document_filename": "doc_a.docx",
        "source_unit_id": "DA::docx_paragraph::2",
        "evidence_needle": "информирование об изменении статуса",
        "evidence_quote": "информирование пользователей об изменении статуса обращения",
    })
    gold_row["required_facts"] = [{"fact_id": "F1", "text": "срок и статус", "evidence_ids": ["DOCA_p1_1", "DOCA_p2_2"]}]
    items = [("c", "не более 16 рабочих часов и информирование об изменении статуса", "doc_a.docx")]
    result = stage_coverage(items, gold_row, {})
    assert result["fact_coverage"] == 1.0
    items_partial = [("c", "не более 16 рабочих часов", "doc_a.docx")]
    assert stage_coverage(items_partial, gold_row, {})["fact_coverage"] == 0.0
