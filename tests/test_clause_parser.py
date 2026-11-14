"""Тесты структурного парсера (аудит v4.1, этап 2): границы, иерархия,
повторяющаяся нумерация, таблицы, документы без нумерации, повреждённые блоки."""

from scripts.build_clause_store import parse_clauses

SHA = "a" * 64


def parse(text, doc="doc"):
    return parse_clauses(doc, SHA, text)


def test_nested_hierarchy_by_numeric_prefix():
    clauses = parse("1. Раздел\n1.1. Пункт\n1.1.1. Подпункт\n1.2. Пункт\n2. Раздел\n")
    by_number = {c["number"]: c for c in clauses}
    assert by_number["1.1"]["parent_id"] == by_number["1"]["clause_id"]
    assert by_number["1.1.1"]["parent_id"] == by_number["1.1"]["clause_id"]
    assert by_number["1.2"]["parent_id"] == by_number["1"]["clause_id"]
    assert by_number["2"]["parent_id"] is None


def test_coordinate_invariant_and_page_break():
    text = "3. Пункт начался\nна странице и продолжился\nпосле разрыва страницы.\n3.1. Следующий\n"
    clauses = parse(text)
    c3 = next(c for c in clauses if c["number"] == "3")
    assert text[c3["start"]:c3["end"]].strip() == c3["full_text"]
    assert "после разрыва страницы" in c3["full_text"]
    c31 = next(c for c in clauses if c["number"] == "3.1")
    assert c3["start"] <= c31["start"] and c31["end"] <= c3["end"]  # вложенность по координатам


def test_trailing_whitespace_not_eaten_from_coordinates():
    text = "1. Пункт\n\n\n2. Другой\n"
    clauses = parse(text)
    c1 = next(c for c in clauses if c["number"] == "1")
    assert c1["end"] > c1["start"] + len(c1["full_text"])  # хвост документа сохранён в координатах
    assert text[c1["start"]:c1["end"]].strip() == c1["full_text"]


def test_repeated_numbering_in_appendix():
    text = "1. Основной\n1.1. Пункт основной\nПриложение\n1. Приложение\n1.1. Пункт приложения\n"
    clauses = parse(text)
    app_11 = [c for c in clauses if c["number"] == "1.1"]
    assert len(app_11) == 2
    parents = {c["parent_id"] for c in app_11}
    assert None not in parents
    # родитель — по префиксу: второй 1.1 привязан к приложенному "1"
    app_ones = [c for c in clauses if c["number"] == "1"]
    assert app_11[-1]["parent_id"] == app_ones[-1]["clause_id"]


def test_ambiguous_parent_is_flagged_not_invented():
    # нумерация без явного родителя "2" — связь не выдумывается
    clauses = parse("1. Раздел\n2.1. Пункт без раздела\n")
    c21 = next(c for c in clauses if c["number"] == "2.1")
    assert c21["parent_id"] is None
    assert c21["parent_ambiguous"] is False


def test_broken_numbering_keeps_text_available():
    text = "Вводный текст без нумерации.\n\n5. Единственный пункт с текстом\n"
    clauses = parse(text)
    assert len(clauses) == 1
    assert "Вводный текст" not in clauses[0]["full_text"]  # не сшивается с пунктом


def test_table_and_empty_blocks():
    text = "1. Пункт\n\n | ячейка | ячейка |\n\n2. Другой\n\n\n"
    clauses = parse(text)
    c1 = next(c for c in clauses if c["number"] == "1")
    assert "| ячейка" in text[c1["start"]:c1["end"]]  # таблица доступна в координатах пункта
    assert len(clauses) == 2  # пустые блоки не порождают пунктов


def test_long_clause_kept_whole():
    body = "длинный текст " * 500
    text = f"7. {body}\n8. Короткий\n"
    clauses = parse(text)
    c7 = next(c for c in clauses if c["number"] == "7")
    assert "длинный текст" in c7["full_text"]
    assert c7["full_text"].count("длинный текст") == 500


def test_references_only_when_number_unique():
    text = "1. Первый\nсм. п. 2\n2. Второй\nприложение\n1. Ещё\nсм. п. 2\n"
    clauses = parse(text)
    ref_sources = [c for c in clauses if c["references"]]
    c2 = next(c for c in clauses if c["number"] == "2" and c["start"] < text.find("приложение"))
    # ссылки на уникальный "2" созданы; повтор "1" не создаёт ложных цепей
    assert all(c2["clause_id"] in c["references"] for c in ref_sources)
    ones = [c for c in clauses if c["number"] == "1"]
    assert all(not any(o["clause_id"] in c["references"] for o in ones) for c in clauses if c is not ones[-1])
