"""Universal Streamlit shell for existing local document services."""
import os
from uuid import uuid4
import streamlit as st
from ui.services import ask_question, fixtures, health
from ui.storage import STORE, ROOT, load_json, save_json, stage_file, delete_file, valid_url
from ui.views import answer_view

DEFAULTS = {"title": os.environ.get("UI_TITLE", "Навигатор знаний"), "theme": "Светлая", "sources_open": False, "advanced": False, "style": "Краткий"}


def new_chat():
    key = uuid4().hex
    st.session_state.chats[key] = {"title": "Новый диалог", "favorite": False, "turns": []}
    st.session_state.active = key


def initialize():
    s = st.session_state
    if "settings" in s:
        return
    s.settings = dict(DEFAULTS)
    s.owner = uuid4().hex
    s.chats = {}
    s.files = []
    s.persist = False
    s.upload_epoch = 0
    s.page = "Ассистент"
    s.mode = "Демонстрационный"
    new_chat()


def persist():
    if st.session_state.persist:
        save_json(STORE / "workspace.json", {"settings": st.session_state.settings, "chats": st.session_state.chats,
                  "files": st.session_state.files, "owner": st.session_state.owner, "active": st.session_state.active})


def preset(question):
    st.session_state.pending_question = question


def assistant_page():
    s = st.session_state
    chat = s.chats[s.active]
    st.title("Ответы, которые можно проверить")
    st.caption("Задайте вопрос по документам. Откройте источники и проверьте основания ответа.")
    if not chat["turns"]:
        st.markdown("#### Начните с вопроса")
        examples = fixtures() if s.mode == "Демонстрационный" else [{"question": x, "label": "Вопрос по вашей базе"} for x in ["Как оформить командировку?", "Как согласовать смету?", "Как забронировать концертный зал?", "Как открыть ФЛС?"]]
        columns = st.columns(2)
        for i, example in enumerate(examples):
            with columns[i % 2]:
                st.button(example["question"], key=f"example{i}", use_container_width=True, on_click=preset, args=(example["question"],))
                st.caption(example["label"])
    for turn in chat["turns"]:
        with st.chat_message("user"):
            st.text(turn["question"])
        with st.chat_message("assistant"):
            answer_view(turn, s.settings)
            a, b = st.columns([1, 2])
            with a:
                st.button("Повторить вопрос", key="repeat"+turn["id"], on_click=preset, args=(turn["question"],))
            with b:
                feedback = st.radio("Оценка ответа", ["Без оценки", "Полезно", "Не помогло"], key="feedback"+turn["id"], horizontal=True)
                comment = st.text_input("Комментарий", key="comment"+turn["id"])
                if st.button("Сохранить отзыв локально", key="save"+turn["id"]):
                    save_json(STORE / "feedback" / (turn["id"]+".json"), {"question": turn["question"], "response": turn["result"], "rating": feedback, "comment": comment})
                    st.success("Отзыв сохранён на этом компьютере. На обучение не отправлен.")
    if "pending_question" in s:
        s.question = s.pop("pending_question")
    with st.form("question_form"):
        st.text_area("Ваш вопрос", key="question", height=100, max_chars=6000, placeholder="Что нужно сделать и какие условия важно учесть?")
        st.caption("Enter — новая строка. Ctrl+Enter — отправить. История диалога не подаётся модели.")
        submit = st.form_submit_button("Получить ответ", type="primary", use_container_width=True)
    st.button("Очистить поле", on_click=preset, args=("",))
    if submit:
        question = s.question.strip()
        if not question:
            st.info("Введите вопрос.")
            return
        request = {"question": question, "document_ids": [], "answer_style": "short" if s.settings["style"] == "Краткий" else "detailed", "include_sources": True, "source_mode": "internal"}
        with st.spinner("Обрабатываю вопрос…"):
            result = ask_question(request, s.mode)
        chat["turns"].append({"id": uuid4().hex, "question": question, "request": request, "result": result})
        chat["title"] = chat["turns"][0]["question"][:75]
        s.pending_question = ""
        persist()
        st.rerun()


def documents_page():
    s = st.session_state
    st.title("Мои документы")
    st.caption("Добавляйте материалы разных проектов. Загруженные файлы хранятся отдельно от поискового индекса.")
    files = st.file_uploader("PDF, DOCX, XLSX · до 20 МБ на файл", type=["pdf", "docx", "xlsx"], accept_multiple_files=True, key=f"upload{s.upload_epoch}")
    if st.button("Сохранить выбранные файлы", disabled=not files):
        for file in files:
            try:
                item = stage_file(file.name, file.getvalue(), s.owner)
                if not any(x["id"] == item["id"] for x in s.files):
                    s.files.append(item)
                st.success(f"{item['name']}: {item['status']}")
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        persist()
    st.info("Обработчик индексации не подключён. Эти файлы пока не участвуют в ответах.")
    query = st.text_input("Поиск по названию")
    kind = st.selectbox("Тип файла", ["Все", "PDF", "DOCX", "XLSX"])
    for item in list(s.files):
        if query.casefold() not in item["name"].casefold() or kind not in ("Все", item["type"]):
            continue
        with st.container(border=True):
            st.text(item["name"])
            st.caption(f"Пользовательский · {item['type']} · {item['size']/1024:.1f} КБ · {item['added']}")
            st.caption(item["status"])
            if st.button("Удалить файл", key="del"+item["id"]):
                delete_file(item)
                s.files.remove(item)
                s.upload_epoch += 1
                persist()
                st.rerun()
    if s.files and st.button("Очистить загруженные файлы"):
        for item in s.files:
            delete_file(item)
        s.files = []
        s.upload_epoch += 1
        persist()
        st.rerun()
    with st.expander("Системные документы · только просмотр"):
        try:
            from answering.bridge import documents
            rows = [{"Название": v["title"], "ID": k, "Источник": "Системный"} for k, v in documents().items() if query.casefold() in v["title"].casefold() and (kind == "Все" or v["title"].lower().endswith('.'+kind.lower()))]
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.caption("Документы не найдены в каталоге.")
        except Exception:
            st.warning("Каталог системных документов недоступен.")
    with st.expander("Добавить источник по ссылке"):
        url = st.text_input("Адрес публичной страницы", placeholder="https://example.org/document")
        if url:
            (st.info if valid_url(url) else st.error)("Ссылка корректна. Импорт ожидает подключения обработчика." if valid_url(url) else "Введите HTTP/HTTPS URL без логина и пароля.")
        st.button("Импортировать ссылку", disabled=True)
        st.caption("Сетевые запросы не выполняются. Допустимые домены, SSRF-защиту и обработку страницы должен проверять backend.")


def history_page():
    s = st.session_state
    st.title("История диалогов")
    only = st.checkbox("Только избранное")
    for key, chat in list(s.chats.items()):
        if only and not chat["favorite"]:
            continue
        with st.container(border=True):
            st.text(chat["title"])
            st.caption(f"Сообщений: {len(chat['turns'])}")
            a, b, c = st.columns(3)
            if a.button("Открыть", key="open"+key):
                s.active = key
                s.pending_page = "Ассистент"
                st.rerun()
            if b.button("Убрать из избранного" if chat["favorite"] else "В избранное", key="fav"+key):
                chat["favorite"] = not chat["favorite"]
                persist()
                st.rerun()
            if c.button("Удалить диалог", key="delete"+key):
                del s.chats[key]
                if not s.chats:
                    new_chat()
                elif s.active == key:
                    s.active = next(iter(s.chats))
                persist()
                st.rerun()


def settings_page():
    s = st.session_state
    st.title("Настройки")
    st.caption("Один интерфейс для регламентов, инструкций, проектной документации и других баз знаний.")
    with st.form("preferences"):
        title = st.text_input("Название рабочего пространства", value=s.settings["title"], max_chars=80)
        theme = st.selectbox("Тема", ["Светлая", "Темная"], index=int(s.settings["theme"] == "Темная"))
        style = st.radio("Предпочтительный вид ответа", ["Краткий", "Подробный"], index=int(s.settings["style"] == "Подробный"), horizontal=True)
        st.caption("Предпочтение передаётся адаптеру. Текущий генератор его пока не использует.")
        opened = st.checkbox("Сразу раскрывать источники", value=s.settings["sources_open"])
        advanced = st.checkbox("Расширенные метаданные и диагностика", value=s.settings["advanced"])
        if st.form_submit_button("Сохранить настройки"):
            s.settings = {"title": title.strip() or DEFAULTS["title"], "theme": theme, "style": style, "sources_open": opened, "advanced": advanced}
            persist()
            st.rerun()
    st.subheader("Конфиденциальность")
    enabled = st.checkbox("Сохранять историю и настройки между запусками на этом компьютере", value=s.persist)
    st.caption("Локальный режим для одного пользователя. По умолчанию история живёт только в сессии. Файлы staging и отзывы сохраняются отдельно до удаления.")
    if enabled != s.persist:
        s.persist = enabled
        if enabled:
            persist()
        else:
            (STORE / "workspace.json").unlink(missing_ok=True)
    if (STORE / "workspace.json").exists() and st.button("Загрузить сохранённое рабочее пространство"):
        try:
            saved = load_json(STORE / "workspace.json", {})
            for key in ("settings", "chats", "files", "owner", "active"):
                if key not in saved:
                    raise ValueError("Сохранённое пространство повреждено")
            s.update(saved)
            s.persist = True
            st.rerun()
        except (ValueError, OSError):
            st.error("Не удалось прочитать сохранённую историю.")
    if st.button("Очистить всю историю"):
        s.chats = {}
        new_chat()
        persist()
        st.rerun()
    if st.button("Удалить сохранённые отзывы"):
        for path in (STORE / "feedback").glob("*.json"):
            path.unlink()
        st.success("Отзывы удалены")
    with st.expander("Параметры поиска · ожидают поддержки backend"):
        st.slider("Количество фрагментов", 1, 20, 6, disabled=True)
        st.multiselect("Ограничить документами", [], disabled=True)
        st.date_input("Дата документа", disabled=True)
        st.selectbox("Область поиска", ["Локальная база", "Разрешённые публичные источники"], disabled=True)


def main():
    st.set_page_config(page_title="Навигатор знаний", page_icon="📚", layout="wide")
    initialize()
    s = st.session_state
    if "pending_page" in s:
        s.page = s.pop("pending_page")
    dark = s.settings["theme"] == "Темная"
    bg, surface, ink, muted = ("#111521", "#1b2132", "#eef0fa", "#b3bdd5") if dark else ("#f7f8fc", "#ffffff", "#17213b", "#5a6580")
    st.markdown(f'''<style>
    .stApp {{background:{bg};color:{ink};}}
    header[data-testid="stHeader"] {{background:{bg};}}
    [data-testid="stToolbar"] {{display:none;}}
    .stButton button,.stDownloadButton button {{background:{surface};color:{ink};border-color:#8892aa70;}}
    .stButton button p,.stDownloadButton button p {{color:inherit!important;}}
    [data-testid="stText"], [data-testid="stText"] *, .stText pre {{color:{ink}!important;white-space:pre-wrap;overflow-wrap:anywhere;}}
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] *, .stCaption, .stCaption *, small {{color:{muted}!important;}}
    [data-baseweb="select"]>div {{background:{surface};color:{ink};}}
    [data-testid="stFileUploaderDropzone"] {{background:{surface};color:{ink};}}
    [data-testid="stFileUploaderDropzone"] button {{background:{surface};color:{ink};font-size:0;}}
    [data-testid="stFileUploaderDropzone"] button::after {{content:"Выбрать файлы";font-size:14px;}}
    [data-testid="stFileUploaderDropzoneInstructions"] span {{font-size:0;}}
    [data-testid="stFileUploaderDropzoneInstructions"] span::after {{content:"Перетащите файлы сюда";font-size:14px;}}
    [data-testid="stFileUploaderDropzoneInstructions"] small {{font-size:0;}}
    [data-testid="stFileUploaderDropzoneInstructions"] small::after {{content:"До 20 МБ · PDF, DOCX, XLSX";font-size:12px;}}

    [data-testid="stAlert"] {{background:{surface};}}
    textarea::placeholder,input::placeholder {{color:{muted}!important;}}
    .stButton button:disabled {{opacity:.5;}}
    .stButton button[kind="primary"] p {{color:white!important;}}

    [data-testid="stSidebar"] {{background:{surface};border-right:1px solid #8892aa30;}}
    .block-container {{max-width:1120px;padding-top:2.5rem;padding-bottom:3rem;}}
    h1 {{font-size:2.25rem!important;letter-spacing:-.045em;line-height:1.15!important;}}
    h2,h3,h4,p,label,[data-testid="stMarkdownContainer"] {{color:{ink};}}
    [data-testid="stCaptionContainer"] p {{color:{muted};}}
    [data-testid="stChatMessage"], [data-testid="stVerticalBlockBorderWrapper"]>div {{border-radius:16px;}}
    [data-testid="stChatMessage"] {{background:{surface};}}
    [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {{background:{surface};color:{ink};}}
    .stButton button,.stDownloadButton button {{border-radius:10px;white-space:normal;height:auto;min-height:42px;}}
    .stButton button[kind="primary"] {{background:#6357d8;color:white;border-color:#6357d8;}}
    .answer-text {{line-height:1.75;overflow-wrap:anywhere;color:{ink};}}
    .answer-text a {{color:{'#b5adff' if dark else '#5146bc'};font-weight:600;}}
    [data-testid="stExpander"] {{background:{surface};border-radius:12px;}}
    summary p {{overflow-wrap:anywhere;}}
    @media(max-width:640px) {{.block-container {{padding:4rem 1rem 1rem;}} h1 {{font-size:1.8rem!important;}}}}
    </style>''', unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("### ◈ " + s.settings["title"])
        st.caption("Ваши документы. Проверяемые ответы.")
        if st.button("＋ Новый диалог", use_container_width=True):
            new_chat()
            s.page = "Ассистент"
            persist()
            st.rerun()
        page = st.radio("Навигация", ["Ассистент", "Документы", "История", "Настройки", "О проекте"], key="page")
        st.divider()
        st.selectbox("Режим работы", ["Демонстрационный", "Подключённый"], key="mode")
        if st.button("Сменить тему", use_container_width=True):
            s.settings["theme"] = "Светлая" if dark else "Темная"
            persist()
            st.rerun()
        st.caption("Локальная обработка · без внешних API")
    if s.mode == "Демонстрационный":
        st.info("Демонстрационный режим — тестовые данные. Retrieval и LLM не подключены к этим ответам.")
    else:
        if "health" not in s or st.button("Проверить подключение"):
            s.health = health()
        st.caption(("Индекс найден · загрузка Retrieval при запросе" if s.health["index"] else "Retrieval: индекс отсутствует") + " | " + ("LLM: отвечает на health-check" if s.health["llm"] else "LLM: недоступна"))
    try:
        if page == "Ассистент": assistant_page()
        elif page == "Документы": documents_page()
        elif page == "История": history_page()
        elif page == "Настройки": settings_page()
        else:
            st.title("О проекте")
            st.write("Универсальный помощник по документам. Название и оформление можно настроить для любой организации или проекта.")
            st.code("Вопрос → UI → адаптер → готовый Retrieval → локальная Qwen → ответ и источники", language=None)
            st.write("Интерфейс показывает сведения сервиса. Он не определяет актуальность редакций и не гарантирует полноту ответа. Сверяйте важные решения с источниками.")
            st.write("Демо использует вымышленные нейтральные документы. Подключённый режим использует существующие answering.bridge и answering.core без изменения алгоритмов.")
            st.caption("Python 3.13 · Streamlit · история локальна · загрузки не отправляются в сеть")
    except (OSError, ValueError, KeyError, TypeError):
        st.error("Не удалось выполнить действие. Проверьте доступность локального хранилища и формат данных.")
