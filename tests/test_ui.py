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
    button(app,'Сменить тему').click().run()
    assert app.session_state.settings['theme']=='Темная'
    assert not app.exception


def test_unavailable(monkeypatch):
    import ui.services as services
    from navigator import rag_service
    from navigator.generation_service import AnswerResponse
    monkeypatch.setattr(rag_service, "ask", lambda *args, **kwargs: AnswerResponse("error", error="LLM недоступна"))
    assert 'LLM' in services.ask_question({'question':'Вопрос'},'Подключённый')['error']


def test_invalid_backend():
    with pytest.raises(ValueError): validate_response({'status':'fake'})



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
