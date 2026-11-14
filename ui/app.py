"""Universal Streamlit shell for existing local document services."""
import os
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from uuid import uuid4
import streamlit as st
from ui.services import ask_question, failure, fixtures, health
from ui.storage import STORE, load_workspace, save_json, stage_file, delete_file
from ui.views import answer_view
from navigator.rag_service import application_config
from navigator.corpus import rebuild

DEFAULTS = {"title": os.environ.get("UI_TITLE", "Навигатор знаний"), "sources_open": False, "advanced": False}
SEARCH_LABELS = {"fast": "Fast · быстрый поиск", "quality": "Quality · поиск полных пунктов"}
GENERATION_LABELS = {"legacy": "Legacy · ответ цитатами", "g2": "G2 · структурированный ответ (эксперимент)"}


@st.cache_resource
def workers():
    return ThreadPoolExecutor(max_workers=2, thread_name_prefix="navigator")


def add_turn(chat, question, request, result):
    chat["turns"].append({"id": uuid4().hex, "question": question, "request": request, "result": result})
    chat["title"] = chat["turns"][0]["question"][:75]
    persist()


@st.fragment(run_every=1.0)
def background_status():
    s = st.session_state
    for key in ("answer_job", "index_job"):
        job = s.get(key)
        if not job:
            continue
        future = job["future"]
        label = "Готовлю ответ" if key == "answer_job" else "Обновляю поисковую базу"
        if not future.done():
            status = label if future.running() else "В очереди"
            st.info(f"{status} · {int(monotonic() - job['started'])} с. Можно переключать разделы.")
            continue
        del s[key]
        try:
            result = future.result()
        except Exception as exc:
            if key == "index_job":
                s.notice = ("error", f"Не удалось обновить базу: {exc}")
                st.rerun()
            result = failure(str(exc))
        if key == "answer_job":
            chat = s.chats.get(job["chat"])
            if chat is not None:
                add_turn(chat, job["request"]["question"], job["request"], result)
                if s.active != job["chat"] or s.page != "Ассистент":
                    s.notice = ("success", "Ответ добавлен в исходный диалог.")
        elif result is not None:
            if s.snapshot and str(result) != s.snapshot:
                invalidate_corpus()
            s.snapshot = str(result)
            s.rebuild_required = False
            persist()
            s.notice = ("success", "База обновлена.")
        st.rerun()


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
    s.mode = os.environ.get("NAVIGATOR_UI_MODE", "Демонстрационный")
    s.snapshot = None
    s.rebuild_required = False
    new_chat()


def persist():
    if st.session_state.persist:
        save_json(STORE / "workspace.json", {"schema_version": 1, "mode": st.session_state.mode,
                  "settings": st.session_state.settings, "chats": st.session_state.chats,
                  "files": st.session_state.files, "snapshot": st.session_state.snapshot,
                  "rebuild_required": st.session_state.rebuild_required, "owner": st.session_state.owner, "active": st.session_state.active})


def preset(question):
    st.session_state.pending_question = question


def assistant_page():
    s = st.session_state
    chat = s.chats[s.active]
    st.title("Ассистент")
    defaults = application_config()
    if s.mode == "Демонстрационный":
        st.info("Режим готовых примеров. Свои документы можно выбрать в настройках.")
    else:
        st.caption(f'{SEARCH_LABELS[s.settings.get("retrieval", defaults["retrieval"])]} / '
                   f'{GENERATION_LABELS[s.settings.get("generation", defaults["generation"])]}')
    job = s.get("answer_job")
    if not chat["turns"] and not (job and job["chat"] == s.active):
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
            st.button("Повторить вопрос", key="repeat"+turn["id"], on_click=preset, args=(turn["question"],))
            with st.expander("Оценить ответ"):
                feedback = st.radio("Оценка ответа", ["Без оценки", "Полезно", "Не помогло"], key="feedback"+turn["id"])
                comment = st.text_input("Комментарий", key="comment"+turn["id"])
                if st.button("Сохранить отзыв локально", key="save"+turn["id"]):
                    save_json(STORE / "feedback" / (turn["id"]+".json"), {"question": turn["question"], "response": turn["result"], "rating": feedback, "comment": comment})
                    st.success("Отзыв сохранён на этом компьютере. На обучение не отправлен.")
    if job and job["chat"] == s.active:
        with st.chat_message("user"):
            st.text(job["request"]["question"])
    if "pending_question" in s:
        s.question = s.pop("pending_question")
    with st.form("question_form"):
        st.text_area("Ваш вопрос", key="question", height=100, max_chars=6000, placeholder="Что нужно сделать и какие условия важно учесть?")
        st.caption("Ctrl+Enter — отправить.")
        submit = st.form_submit_button("Получить ответ", type="primary", use_container_width=True, disabled=bool(job))
    st.button("Очистить поле", on_click=preset, args=("",))
    if submit:
        question = s.question.strip()
        if not question:
            st.info("Введите вопрос.")
            return
        if s.mode == "Подключённый" and (s.rebuild_required or s.get("index_job")):
            st.warning("Перестройте базу во вкладке «Документы».")
            return
        defaults = application_config()
        request = {"question": question, "retrieval": s.settings.get("retrieval", defaults["retrieval"]),
                   "generation": s.settings.get("generation", defaults["generation"]),
                   "snapshot": s.snapshot, "diagnostics": s.settings["advanced"]}
        if s.mode == "Демонстрационный":
            add_turn(chat, question, request, ask_question(request, s.mode))
        else:
            s.answer_job = {"future": workers().submit(ask_question, request, s.mode),
                            "request": request, "chat": s.active, "started": monotonic()}
        s.pending_question = ""
        st.rerun()


def invalidate_corpus():
    s = st.session_state
    s.rebuild_required = True
    for chat in s.chats.values():
        chat["turns"] = [turn for turn in chat["turns"] if turn["result"]["metadata"].get("mode") == "Демонстрационный"]


def documents_page():
    s = st.session_state
    st.title("Мои документы")
    st.caption("Загрузите файлы и обновите поисковую базу.")
    busy = bool(s.get("index_job") or s.get("answer_job"))
    files = st.file_uploader("PDF, DOCX, XLSX · до 20 МБ на файл", type=["pdf", "docx", "xlsx"], accept_multiple_files=True, key=f"upload{s.upload_epoch}", disabled=busy)
    if st.button("Сохранить выбранные файлы", disabled=busy or not files):
        for file in files:
            try:
                item = stage_file(file.name, file.getvalue(), s.owner)
                if not any(x["id"] == item["id"] for x in s.files):
                    s.files.append(item)
                    s.rebuild_required = True
                st.success(f"{item['name']}: {item['status']}")
            except (ValueError, OSError) as exc:
                st.error(str(exc))
        persist()
    if st.button("Построить или обновить базу", disabled=busy):
        inputs = [(item["name"], STORE / "staging" / s.owner / item["id"]) for item in s.files]
        s.index_job = {"future": workers().submit(rebuild, STORE / "corpus" / s.owner, inputs),
                       "started": monotonic()}
        st.rerun()
    if s.rebuild_required:
        st.info("Список документов изменился. Требуется обновление базы.")
    query = st.text_input("Поиск по названию")
    kind = st.selectbox("Тип файла", ["Все", "PDF", "DOCX", "XLSX"])
    for item in list(s.files):
        if query.casefold() not in item["name"].casefold() or kind not in ("Все", item["type"]):
            continue
        with st.container(border=True):
            st.text(item["name"])
            st.caption(f"Пользовательский · {item['type']} · {item['size']/1024:.1f} КБ · {item['added']}")
            st.caption("Ожидает обновления базы" if s.rebuild_required else "В поисковой базе")
            if st.button("Удалить файл", key="del"+item["id"], disabled=busy):
                delete_file(item)
                s.files.remove(item)
                invalidate_corpus()
                s.upload_epoch += 1
                persist()
                st.rerun()
    if s.files and st.button("Очистить загруженные файлы", disabled=busy):
        for item in s.files:
            delete_file(item)
        s.files = []
        invalidate_corpus()
        s.upload_epoch += 1
        persist()
        st.rerun()
    with st.expander("Системные документы · только просмотр"):
        try:
            from navigator.settings import DATA
            rows = [{"Название": path.name} for path in sorted((DATA / "raw").rglob("*"))
                    if path.is_file() and query.casefold() in path.name.casefold()
                    and (kind == "Все" or path.suffix.lower() == "." + kind.lower())]
            if rows:
                st.dataframe(rows, hide_index=True, use_container_width=True)
            else:
                st.caption("Документы не найдены в каталоге.")
        except Exception:
            st.warning("Каталог системных документов недоступен.")


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
    defaults = application_config()
    st.subheader("Ответы")
    with st.form("preferences"):
        mode = st.selectbox("Источник ответов", ["Подключённый", "Демонстрационный"],
                            index=int(s.mode == "Демонстрационный"),
                            format_func=lambda mode: "Свои документы" if mode == "Подключённый" else "Готовые примеры")
        retrieval = st.selectbox("Поиск по документам", list(SEARCH_LABELS),
                                 index=list(SEARCH_LABELS).index(s.settings.get("retrieval", defaults["retrieval"])),
                                 format_func=SEARCH_LABELS.get)
        generation = st.selectbox("Генератор ответа", list(GENERATION_LABELS),
                                  index=list(GENERATION_LABELS).index(s.settings.get("generation", defaults["generation"])),
                                  format_func=GENERATION_LABELS.get)
        st.caption("Поиск и модель используются для своих документов. G2 может отвечать несколько минут.")
        opened = st.checkbox("Сразу раскрывать источники", value=s.settings["sources_open"])
        advanced = st.checkbox("Показывать диагностику", value=s.settings["advanced"])
        title = st.text_input("Название рабочего пространства", value=s.settings["title"], max_chars=80)
        if st.form_submit_button("Сохранить настройки"):
            s.mode = mode
            s.settings.update(title=title.strip() or DEFAULTS["title"], retrieval=retrieval,
                              generation=generation, sources_open=opened, advanced=advanced)
            persist()
            st.rerun()
    st.caption("Светлая и тёмная темы доступны в меню ⋮.")
    if s.mode == "Подключённый":
        if st.button("Проверить подключение"):
            status = health(s.snapshot, s.settings.get("generation", defaults["generation"]))
            st.write("Индекс готов" if status["index"] else "Индекс отсутствует")
            st.write("Локальная модель доступна" if status["llm"] else "Локальная модель недоступна")
    st.subheader("Конфиденциальность")
    enabled = st.checkbox("Сохранять историю и настройки между запусками на этом компьютере", value=s.persist)
    st.caption("Локальный режим для одного пользователя. По умолчанию история живёт только в сессии. Файлы staging и отзывы сохраняются отдельно до удаления.")
    if enabled != s.persist:
        s.persist = enabled
        if enabled:
            persist()
        else:
            (STORE / "workspace.json").unlink(missing_ok=True)
    if (STORE / "workspace.json").exists() and st.button("Загрузить сохранённое рабочее пространство", disabled=bool(s.get("index_job") or s.get("answer_job"))):
        try:
            s.update(load_workspace(STORE / "workspace.json", DEFAULTS))
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


def main():
    st.set_page_config(page_title="Навигатор знаний", page_icon="📚", layout="wide")
    application_config()
    initialize()
    s = st.session_state
    if "pending_page" in s:
        s.page = s.pop("pending_page")
    st.markdown("""<style>
    .block-container {max-width: 1120px;}
    .answer-text {line-height: 1.65; overflow-wrap: anywhere;}
    [data-testid="stText"] pre {white-space: pre-wrap; overflow-wrap: anywhere;}
    [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"],
    [data-testid="stBaseButton-secondaryDownload"],
    [data-testid="stBaseButton-secondaryFormSubmit"], [data-testid="stBaseButton-primaryFormSubmit"] {
        white-space: normal; height: auto; min-height: 2.5rem;
    }
    [data-testid="stBaseButton-secondary"] p, [data-testid="stBaseButton-secondaryDownload"] p {
        overflow-wrap: anywhere;
    }
    </style>""", unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("### ◈ " + s.settings["title"])
        st.caption("Ваши документы. Проверяемые ответы.")
        if st.button("＋ Новый диалог", use_container_width=True):
            new_chat()
            s.pending_page = "Ассистент"
            persist()
            st.rerun()
        page = st.radio("Навигация", ["Ассистент", "Документы", "История", "Настройки", "О проекте"], key="page")
    if s.get("answer_job") or s.get("index_job"):
        background_status()
    if notice := s.pop("notice", None):
        level, message = notice
        (st.error if level == "error" else st.success)(message)
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
            st.write("Демо использует вымышленные нейтральные документы. Подключённый режим использует Retriever v4.1 и выбранный локальный генератор.")
            st.caption("Python 3.13 · Streamlit · история локальна · загрузки не отправляются в сеть")
    except (OSError, ValueError, KeyError, TypeError):
        st.error("Не удалось выполнить действие. Проверьте доступность локального хранилища и формат данных.")
