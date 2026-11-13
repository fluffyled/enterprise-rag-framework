from navigator.adaptive_strategy import STRATEGY_BY_TYPE, choose_strategy, classify_question


def test_single_fact_by_default():
    decision = choose_strategy("Кто утверждает смету подразделения?")
    assert decision["type"] == "single_fact"
    assert decision["strategy"] == "top_k"


def test_multi_requirement_by_subtasks():
    decision = choose_strategy("Как оформить командировку и кто оплачивает проживание?", subtasks=[{"id": "q0"}, {"id": "q1"}])
    assert decision["type"] == "multi_requirement"
    assert decision["strategy"] == "protected_coverage"


def test_multi_requirement_by_enumeration():
    decision = classify_question("Назовите сроки согласования, оплаты и отчётности по договору.")
    assert decision["type"] == "multi_requirement"


def test_multi_document_by_doc_types():
    decision = choose_strategy("Что требует приказ о бюджете и регламент по сметам?")
    assert decision["type"] == "multi_document"
    assert decision["strategy"] == "coverage"


def test_uncertain_on_weak_signals():
    decision = classify_question("Какой срок действует в регламенте, и кто подписывает документ?")
    assert decision["type"] == "uncertain"
    assert choose_strategy("Какой срок действует в регламенте, и кто подписывает документ?")["strategy"] == "top_k"


def test_confidence_and_diagnostics_present():
    decision = choose_strategy("Перечислите документы, приложенные к приказу, и сроки их хранения.")
    assert 0.0 <= decision["confidence"] <= 1.0
    assert decision["reason"]
    assert set(decision["signals"]) >= {"subtasks", "list_markers", "enum_cue", "doc_types", "years"}


def test_strategy_map_complete():
    assert set(STRATEGY_BY_TYPE) == {"single_fact", "multi_requirement", "multi_document", "uncertain"}
