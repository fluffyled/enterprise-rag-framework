import answering
import pytest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from ui.services import fixtures, ask_question, validate_response
from ui import storage


def test_demo_and_unknown():
    for item in fixtures():
        result = ask_question({"question":item["question"]}, "Демонстрационный")
        assert result['status'] == item['response']['status']
        validate_response(result)
    assert ask_question({'question':'unknown'},'Демонстрационный')['status']=='error'


def test_staging(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, 'STORE', tmp_path)
    owner='a'*32
    item=storage.stage_file('../../name.pdf',b'%PDF-test',owner)
    assert item['name']=='name.pdf'
    assert (tmp_path/'staging'/owner/item['id']).exists()
    storage.delete_file(item)
    assert not (tmp_path/'staging'/owner/item['id']).exists()
    for name,body in [('a.exe',b'x'),('a.pdf',b''),('a.pdf',b'x'*(storage.MAX_BYTES+1))]:
        with pytest.raises(ValueError): storage.stage_file(name,body,owner)
    assert not storage.valid_url('javascript:alert(1)')
    assert not storage.valid_url('https://user:password@example.org')
    assert storage.valid_url('https://example.org/doc')


def button(app,label):
    return next(b for b in app.button if b.label==label)


def test_ui_flow():
    app=AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py', default_timeout=15).run()
    assert not app.exception
    button(app,'Кто подтверждает бронирование?').click().run()
    assert app.text_area[0].value=='Кто подтверждает бронирование?'
    button(app,'Получить ответ').click().run()
    assert not app.exception
    assert len(app.session_state.chats[app.session_state.active]['turns'])==1
    app.run()
    assert len(app.session_state.chats[app.session_state.active]['turns'])==1
    app.radio(key='page').set_value('История').run()
    button(app,'В избранное').click().run()
    button(app,'Открыть').click().run()
    assert not app.exception
    button(app,'＋ Новый диалог').click().run()
    assert len(app.session_state.chats)==2
    app.radio(key='page').set_value('История').run()
    button(app,'Удалить диалог').click().run()
    assert len(app.session_state.chats)==1
    app.radio(key='page').set_value('Документы').run()
    assert not app.exception
    app.radio(key='page').set_value('Настройки').run()
    app.selectbox[0].set_value("Подключённый")
    app.selectbox[1].set_value("quality")
    app.selectbox[2].set_value("g2")
    button(app, "Сохранить настройки").click().run()
    assert app.session_state.mode == "Подключённый"
    assert app.session_state.settings["retrieval"] == "quality"
    assert app.session_state.settings["generation"] == "g2"
    assert not app.exception


@pytest.mark.parametrize("operation", ["answer", "index"])
def test_navigation_during_background_work(monkeypatch, tmp_path, operation):
    from concurrent.futures import Future
    from ui import app as ui_app
    from ui.services import failure

    future = Future()
    monkeypatch.setattr(ui_app, "workers", lambda: type("Worker", (), {"submit": lambda self, *args: future})())
    path = Path(__file__).resolve().parents[1] / "app.py"
    app = AppTest.from_file(path, default_timeout=15).run()
    if operation == "answer":
        app.session_state.mode = "Подключённый"
        app.text_area(key="question").set_value("Вопрос в фоне")
        button(app, "Получить ответ").click().run()
        job_key = "answer_job"
    else:
        app.radio(key="page").set_value("Документы").run()
        button(app, "Построить или обновить базу").click().run()
        job_key = "index_job"
    assert app.session_state[job_key]["future"] is future
    app.radio(key="page").set_value("Настройки").run()
    assert app.title[0].value == "Настройки"
    assert app.session_state[job_key]["future"] is future
    future.set_result(failure("Модель недоступна") if operation == "answer" else tmp_path)
    app.run()
    assert job_key not in app.session_state
    if operation == "answer":
        turns = app.session_state.chats[app.session_state.active]["turns"]
        assert len(turns) == 1 and turns[0]["question"] == "Вопрос в фоне"
    else:
        assert app.session_state.snapshot == str(tmp_path)
    assert not app.exception


def test_unavailable(monkeypatch):
    import ui.services as services
    from navigator import rag_service
    from navigator.generation_service import AnswerResponse
    monkeypatch.setattr(rag_service, "ask", lambda *args, **kwargs: AnswerResponse("error", error="LLM недоступна"))
    assert 'LLM' in services.ask_question({'question':'Вопрос'},'Подключённый')['error']


def test_invalid_backend():
    with pytest.raises(ValueError): validate_response({'status':'fake'})


def test_document_number_does_not_become_a_citation(monkeypatch):
    from ui import views
    rendered = []
    monkeypatch.setattr(views.st, "markdown", lambda text, **_: rendered.append(text))
    views.linked_text("Пункт [1] [источник 1]", {
        "metadata": {"mode": "Подключённый"}, "sources": [{}],
    }, "turn")
    assert "Пункт [1] <a" in rendered[0]
    assert rendered[0].count('href="#turn-s1"') == 1


def test_steps_precede_extra_summary_and_sources_without_repeating_rule():
    from ui.views import export_text

    rule = "Запрет действует после утверждения регламента:\n\uf02d кроме конкурсных договоров. [источник 1]"
    result = {"status": "partial", "answer": rule + "\n\nДополнительное условие.",
              "steps": ["Запрещено · " + rule + " · Условие — после утверждения"],
              "sources": [{"document_title": "Регламент", "excerpt": "Текст источника"}],
              "metadata": {}, "conflicts": [], "missing_information": []}
    exported = export_text("Выдадут ли заём?", result)
    assert exported.count("Запрет действует") == 1
    assert exported.index("1. Запрещено") < exported.index("Дополнительное условие.") < exported.index("Текст источника")
    assert "• кроме конкурсных договоров." in exported



def test_export_and_all_status_views():
    from ui.views import export_text
    for item in fixtures():
        result=ask_question({'question':item['question']},'Демонстрационный')
        exported=export_text(item['question'],result)
        assert item['question'] in exported
        for source in result['sources']:
            assert source['excerpt'] in exported
            assert source['document_title'] in exported
        app=AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py',default_timeout=15).run()
        button(app,item['question']).click().run()
        button(app,'Получить ответ').click().run()
        assert not app.exception


def test_empty_form_does_not_add_turn():
    app=AppTest.from_file(Path(__file__).resolve().parents[1] / 'app.py',default_timeout=15).run()
    button(app,'Получить ответ').click().run()
    assert not app.session_state.chats[app.session_state.active]['turns']
    assert not app.exception
