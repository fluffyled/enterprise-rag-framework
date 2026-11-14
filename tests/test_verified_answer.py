from navigator.verified_answer import _action_supported, _field_supported, build_evidence_blocks, verify_plan


def make_blocks():
    return [
        {"id": "block_1", "document": "reg.pdf", "clause": "3.1", "page": 2, "text": "3.1. Обращение подаётся через систему управления обращениями на mipt.ru/it/support или на helpdesk@mipt.ru."},
        {"id": "block_2", "document": "reg.pdf", "clause": "4.2", "page": 3, "text": "4.2. Время первичной обработки составляет не более 16 рабочих часов."},
    ]


def test_supported_step_passes():
    blocks = make_blocks()
    step = {"action": "Подать обращение через систему управления обращениями", "actor": None, "condition": None, "deadline": None, "evidence_id": "block_1"}
    assert _action_supported(step, blocks[0]) is True


def test_invented_deadline_is_stripped_not_fatal():
    blocks = make_blocks()
    step = {"action": "Подать обращение через систему", "actor": None, "condition": None, "deadline": "не более 3 рабочих дней", "evidence_id": "block_1"}
    assert _action_supported(step, blocks[0]) is True
    assert _field_supported(step["deadline"], blocks[0]) is False
    supported, missing = verify_plan({"steps": [step], "missing_information": []}, blocks)
    assert len(supported) == 1
    assert supported[0]["deadline"] is None


def test_unknown_evidence_id_moves_to_missing():
    blocks = make_blocks()
    plan = {"steps": [{"action": "Сделать что-то", "evidence_id": "block_99"}], "missing_information": []}
    supported, missing = verify_plan(plan, blocks)
    assert supported == []
    assert any("нет источника" in item for item in missing)


def test_unsupported_step_moves_to_missing():
    blocks = make_blocks()
    plan = {"steps": [{"action": "Оплатить счёт в банке", "evidence_id": "block_1"}], "missing_information": ["порядок закрытия"]}
    supported, missing = verify_plan(plan, blocks)
    assert supported == []
    assert any("не подтверждено" in item for item in missing)
    assert "порядок закрытия" in missing


def test_verify_plan_keeps_supported_step_with_quote():
    blocks = make_blocks()
    plan = {"steps": [{"action": "Подать обращение через систему управления обращениями", "evidence_id": "block_1"}], "missing_information": []}
    supported, missing = verify_plan(plan, blocks)
    assert len(supported) == 1
    assert supported[0]["clause"] == "3.1"
    assert "mipt.ru/it/support" in supported[0]["quote"]
    assert missing == []


def test_blocks_built_from_documents():
    from haystack import Document

    docs = [Document(content="текст", meta={"document_id": "a.pdf", "clause_number": "3.1", "page": "2"})]
    blocks = build_evidence_blocks(docs)
    assert blocks[0]["id"] == "block_1"
    assert blocks[0]["clause"] == "3.1"
