from pathlib import Path
import json
import hashlib
import answering  # Configure disk D before third-party imports.
import streamlit as st
from answering.catalog import DATA, topics, assignments, validate_topics, read_assignments, csv_text
from answering.contracts import read_bundle
from answering.core import generate
from answering.grounded import grounded_answer
from answering.bridge import BaselineSearch, documents, external_sources, save_external
from answering.web import load_url

st.set_page_config(page_title="Документы МФТИ", layout="centered")
st.title("Вопрос по документам МФТИ")
st.caption("Короткие ответы с цитатами. Обработка вопросов и документов — на этом компьютере.")
DATA.mkdir(exist_ok=True)
try:
    topic_names=topics(); mapping=assignments()
except (ValueError,KeyError,TypeError) as exc:
    st.error(f"Ошибка каталога тем: {exc}");st.stop()
qa, sources_tab=st.tabs(["Задать вопрос","Источники и темы"])

with sources_tab:
    st.subheader("Открытые страницы")
    links=st.text_area("Ссылки — по одной на строке",help="HTML, текст и PDF с текстовым слоем. Без входа в аккаунт и без выполнения JavaScript.")
    if st.button("Загрузить страницы"):
        urls=[u.strip() for u in links.splitlines() if u.strip()]
        if not 1 <= len(urls) <= 5: st.error("Укажите от 1 до 5 ссылок за один раз.")
        else:
            for url in urls:
                try:
                    with st.spinner("Загружаю открытый источник…"):
                        fragments,info=load_url(url);save_external(fragments,info)
                    st.success(f"Источник загружен: {info['fragments']} фрагментов.")
                except Exception as exc: st.error(f"Не удалось загрузить источник: {exc}")
    st.subheader("Темы")
    if not topic_names: st.info("Утверждённый список тем ещё не загружен. Документы доступны без фильтра; темы не назначаются автоматически.")
    topic_file=st.file_uploader("Загрузить утверждённые темы JSON",type=["json"],key="topics")
    if topic_file and st.button("Применить список тем"):
        try:
            payload=json.loads(topic_file.getvalue());new_topics=validate_topics(payload)
            missing={t for ids in mapping.values() for t in ids}-set(new_topics)
            if missing: raise ValueError("Сначала уберите из разметки удаляемые темы")
            (DATA/"topics.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8");st.rerun()
        except Exception as exc: st.error(str(exc))
    docs=documents()
    rows=[{"document_id":key,"Название":value["title"],"topic_ids":";".join(mapping.get(key,()))} for key,value in docs.items()]
    if rows:
        edited=st.data_editor(rows,disabled=["document_id","Название"],hide_index=True,use_container_width=True,key="assignments")
        st.caption("В topic_ids перечислите ID тем через точку с запятой. Один документ может относиться к нескольким темам.")
        if st.button("Сохранить разметку"):
            try:
                text=csv_text({r["document_id"]:tuple(x.strip() for x in r["topic_ids"].split(";") if x.strip()) for r in edited})
                read_assignments(text,topic_names)
                (DATA/"document_topics.csv").write_text(text,encoding="utf-8");st.rerun()
            except Exception as exc:st.error(str(exc))
        st.download_button("Скачать CSV для массовой разметки",csv_text({key:mapping.get(key,()) for key in docs}),"document_topics.csv","text/csv")
    uploaded=st.file_uploader("Импорт разметки CSV",type=["csv"])
    if uploaded and st.button("Применить CSV"):
        try:
            text=uploaded.getvalue().decode("utf-8-sig");parsed=read_assignments(text,topic_names)
            if set(parsed)-set(docs):raise ValueError("В разметке неизвестные документы")
            (DATA/"document_topics.csv").write_text(csv_text(parsed),encoding="utf-8");st.rerun()
        except Exception as exc:st.error(str(exc))
    for source in external_sources():
        info=source["info"]
        st.caption(f"Загружено {info['retrieved_at']}; фрагментов {info['fragments']}")
        st.link_button("Открыть загруженный источник",info["url"])

@st.cache_resource(max_entries=1)
def get_search(index_stamp,external_stamp):return BaselineSearch()

with qa:
    mode=st.radio("Источники ответа",["Локальная база и загруженные страницы","Фрагменты первого разработчика (JSON)"],label_visibility="collapsed")
    bundle=None
    if mode.endswith("(JSON)"):
        file=st.file_uploader("Результат поиска schema_version=1",type=["json"],key="bundle")
        if file:
            try:bundle=read_bundle(json.loads(file.getvalue()))
            except Exception as exc:st.error(f"Неверный контракт: {exc}")
    selected=st.multiselect("Темы — необязательно",list(topic_names),format_func=lambda x:topic_names[x])
    question=st.text_input("Ваш вопрос",placeholder="Кто инициирует подбор сотрудника?",max_chars=2000)
    grounded = st.checkbox("Связный ответ с проверкой утверждений (эксперимент)")
    fingerprint = json.dumps({"q":question,"grounded":grounded,"mode":mode,"topics":selected,"bundle":[f.to_dict() for f in (bundle or [])],
        "index":(DATA/"index.json").stat().st_mtime_ns if (DATA/"index.json").exists() else 0,
        "external":(DATA/"external_sources.json").stat().st_mtime_ns if (DATA/"external_sources.json").exists() else 0,
        "mapping":mapping},ensure_ascii=False,sort_keys=True)
    request_key=hashlib.sha256(fingerprint.encode()).hexdigest()
    if st.button("Получить короткий ответ",type="primary"):
        if not question.strip():st.info("Введите вопрос.")
        else:
            try:
                with st.spinner("Ищу подтверждение в документах…"):
                    if mode.endswith("(JSON)"):
                        if bundle is None:raise ValueError("Загрузите результат поиска")
                        evidence=[f for f in bundle if not selected or set(selected)&set(f.topic_ids)]
                    else:
                        index=DATA/"index.json";external=DATA/"external_sources.json"
                        if not index.exists():raise ValueError("Подключите поисковый индекс первой части либо выберите JSON-режим")
                        search=get_search(index.stat().st_mtime_ns,external.stat().st_mtime_ns if external.exists() else 0)
                        evidence=search.search(question,selected,mapping)
                    result = grounded_answer(question, evidence) if grounded else generate(question, evidence)
                st.session_state["last_answer"]=result
                st.session_state["last_answer_key"]=request_key
            except Exception as exc:st.error(str(exc));st.session_state.pop("last_answer",None)
    result=st.session_state.get("last_answer")
    if result and st.session_state.get("last_answer_key")==request_key:
        if result.get("fallback"):
            st.caption("Показаны исходные цитаты после проверки черновика.")
        if grounded and "missing" in result:
            if result["status"] == "insufficient":
                st.warning("Подтверждённых сведений для ответа не найдено.")
            elif result["status"] == "partial":
                st.warning("Часть вопроса осталась без подтверждённого ответа.")
            for index, item in enumerate(result["answer"]):
                st.text(item["text"])
                source = next(e for e in item["sources"] if e["id"] == item["review"]["evidence_id"])
                st.caption(f"{source['title']} · {source['locator']}")
                with st.expander("Подтверждающая цитата"):
                    st.text(item["review"]["quote"])
                    if source["url"]:
                        st.link_button(f"Открыть источник {index + 1}", source["url"])
            for requirement in dict.fromkeys(result["missing"]):
                st.text(f"Нет подтверждения — {requirement}")
        elif result["status"]=="error":st.error(result["error"])
        elif result["status"]=="insufficient":st.warning("В найденных документах недостаточно сведений для подтверждённого ответа.")
        else:
            if result["status"]=="partial":st.warning("Найден только частичный ответ.")
            if result["status"]=="conflict":st.warning("Возможное противоречие: проверьте обе цитаты.")
            for item in result["answer"]:
                st.text(item["quote"]);st.caption(f"{item['title']} · {item['locator']}")
            if result["steps"]:
                with st.expander("Порядок действий из документов"):
                    for i,item in enumerate(result["steps"],1):st.text(f"{i}. {item['quote']}")
            for conflict in result["conflicts"]:
                for side in ["left","right"]:
                    item=conflict[side];st.text(item["quote"]);st.caption(f"{item['title']} · {item['locator']}")
            with st.expander("Проверить источники"):
                seen=set()
                for item in result["answer"]+result["steps"]+[x[side] for x in result["conflicts"] for side in ["left","right"]]:
                    key=(item["fragment_id"],item["quote"])
                    if key in seen:continue
                    seen.add(key);st.text(item["title"]+" · "+item["locator"]);st.text(item["quote"])
                    if item["url"]:st.link_button("Открыть источник",item["url"])
            st.caption("Цитаты проверены на совпадение с текстом. Их применимость и полнота процедуры требуют проверки.")
