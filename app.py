from navigator.settings import INDEX
import streamlit as st
from navigator.retrieval import Retriever
from navigator.answer import answer, ABSTAIN
st.set_page_config(page_title="Навигатор сотрудника", layout="wide")
st.title("Навигатор сотрудника по регламентам")
st.caption("Локальная обработка. Ответы приводятся дословными выдержками с проверкой цитат.")
if not INDEX.exists():
    st.info("База документов ещё не подготовлена. Выполните индексацию по README.")
    st.stop()
@st.cache_resource
def get_retriever(stamp): return Retriever()
try:
    retriever = get_retriever(INDEX.stat().st_mtime_ns)
except Exception as e:
    st.error(f"Не удалось открыть базу: {e}"); st.stop()
q = st.text_input("Вопрос сотрудника", placeholder="Кто инициирует поиск сотрудника на вакансию?")
if st.button("Найти ответ", type="primary") and q.strip():
    with st.spinner("Ищу документы и проверяю цитаты…"):
        docs = retriever.search(q)
        result = answer(q, docs)
    if result["status"] == "error":
        st.error("Не удалось получить проверяемый ответ от локальной модели.")
        st.caption(result.get("error", ""))
    elif result["status"] == "insufficient": st.warning(ABSTAIN)
    else:
        st.subheader("Ответ из документов")
        for item in result["answer"]: st.write(f'{item["quote"]} [{item["source"]}]')
        if result["steps"]:
            st.subheader("Порядок действий из источников")
            for i, item in enumerate(result["steps"], 1): st.write(f'{i}. {item["quote"]} [{item["source"]}]')
        for conflict in result["conflicts"]:
            st.warning(f'Возможное противоречие, требует проверки: [{conflict["left"]}] {conflict["left_quote"]} / [{conflict["right"]}] {conflict["right_quote"]}')
    st.info("Актуальность редакций не подтверждена. Даты и отменяющие приказы необходимо сверять по источникам. Отсутствие предупреждения о конфликте не доказывает отсутствие противоречий.")
    st.subheader("Найденные источники")
    for i, d in enumerate(docs, 1):
        with st.expander(f'[{i}] {d.meta["name"]} — {d.meta["locator"]}', expanded=i == 1):
            st.text(d.content)
            st.caption(f'Раздел: {d.meta.get("section") or "не определён"}; дата из имени: {d.meta.get("date_hint") or "не указана"}; OCR: {d.meta.get("ocr", False)}; ID: {d.id}')
