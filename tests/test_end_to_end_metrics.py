from navigator.evaluation.end_to_end import aggregate_answer_metrics, evaluate_answer, failure_category


def case(answerable=True):
    return {"answerable": answerable, "question_type": "procedure", "evidence_groups": [{"alternatives": [{"text": "подать заявку в течение пяти дней"}]}] if answerable else []}


def test_answer_metrics_separate_literal_and_semantic_validation():
    result = {"status": "supported_quotes", "answer": [{"source": 1, "quote": "Нужно подать заявку в течение пяти дней."}], "steps": []}
    metrics = evaluate_answer(result, case())
    assert metrics["answer_correctness_proxy"]
    assert metrics["citation_precision_proxy"] == 1
    assert metrics["citation_recall_proxy"] == 1
    assert metrics["literal_citation_validation"]
    assert metrics["semantic_citation_review"] is None
    assert failure_category(result, metrics, True, True) is None


def test_abstention_and_failure_attribution():
    insufficient = {"status": "insufficient", "answer": [], "steps": []}
    assert evaluate_answer(insufficient, case(False))["answer_correctness_proxy"]
    rows = [{"answerable": True, "answer_metrics": evaluate_answer(insufficient, case())}, {"answerable": False, "answer_metrics": evaluate_answer(insufficient, case(False))}]
    aggregate = aggregate_answer_metrics(rows)
    assert aggregate["abstention_precision"] == 0.5
    assert aggregate["abstention_recall"] == 1
    assert aggregate["false_abstentions"] == 1
    assert failure_category(insufficient, rows[0]["answer_metrics"], False, False) == "evidence_absent_from_candidates"
    assert failure_category(insufficient, rows[0]["answer_metrics"], True, True) == "false_abstention"
    unsupported = {"status": "supported_quotes", "answer": [{"source": 1, "quote": "неподтверждённый ответ"}], "steps": []}
    metrics = evaluate_answer(unsupported, case(False))
    assert failure_category(unsupported, metrics, False, False, answerable=False) == "missed_abstention"
