"""Reusable response presentation; source text is never executed as HTML."""
import html
import json
import re
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components
from navigator.corpus import fingerprint
from navigator.settings import DATA
from ui.storage import STORE, valid_url

LABELS = {"answered": "Ответ по документам", "partial": "Частичный ответ", "insufficient": "Недостаточно информации", "conflict": "Возможное противоречие", "error": "Техническая ошибка"}


def export_text(question, result):
    lines = [f"# {question}", "", f"Режим: {result['metadata'].get('mode', '')}", f"Статус: {LABELS[result['status']]}", "", result["answer"]]
    lines += [f"{i}. {step}" for i, step in enumerate(result["steps"], 1)]
    lines += result["conflicts"] + result["missing_information"]
    if result.get("error"):
        lines.append(result["error"])
    for i, s in enumerate(result["sources"], 1):
        lines += ["", f"[{i}] {s['document_title']} — {s.get('locator', '')}", s["excerpt"]]
    return "\n".join(lines)


def copy_button(text, label="Скопировать ответ"):
    payload = json.dumps(text, ensure_ascii=True).replace("<", "\\u003c")
    components.html('''<button style="padding:9px 14px;border:1px solid #888;border-radius:8px;background:#f0f2f8;color:#30394f;cursor:pointer" onclick="copyText()">''' + html.escape(label) + '''</button><span id="status" role="status"></span>
<script>async function copyText(){const t=''' + payload + ''';try{await navigator.clipboard.writeText(t);document.getElementById('status').textContent=' Скопировано';}catch(e){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();const ok=document.execCommand('copy');a.remove();document.getElementById('status').textContent=ok?' Скопировано':' Используйте экспорт';}}</script>'''.replace('\n+', '\n'), height=45)


def linked_text(text, result, prefix):
    escaped = html.escape(text)
    def link(match):
        number = int(match.group(1))
        if 1 <= number <= len(result["sources"]):
            return f'<a href="#{prefix}-s{number}" target="_self">[{number}]</a>'
        return match.group(0)
    st.markdown('<div class="answer-text">' + re.sub(r"\[(\d+)\]", link, escaped).replace('\n', '<br>') + '</div>', unsafe_allow_html=True)


def local_document(source):
    relative = source.get("relative_path")
    version = source.get("document_version")
    if not relative or not version:
        return None
    path = Path(relative)
    if path.parts and path.parts[0] == ".uploads":
        if len(path.parts) != 3:
            return None
        root = STORE / "staging" / st.session_state.owner
        candidate = root / (path.parts[1] + path.suffix.lower())
    else:
        root = DATA / "raw"
        candidate = root / path
    candidate = candidate.resolve()
    if candidate.is_relative_to(root.resolve()) and candidate.is_file() and fingerprint(candidate) == version:
        return candidate
    return None


def answer_view(turn, settings):
    result, key = turn["result"], turn["id"]
    st.caption(result["metadata"].get("mode", "") + " · " + LABELS[result["status"]])
    status = result["status"]
    if status == "error":
        st.error(result.get("error", "Ошибка сервиса"))
    elif status == "insufficient":
        st.info("В доступных документах недостаточно информации для подтвержденного ответа.")
    elif status == "partial":
        st.warning("Ответ может быть неполным. Проверьте условия и исключения в источниках.")
    elif status == "conflict":
        st.warning("Возможное противоречие. Требуется проверка связанных источников.")
    if result["answer"]:
        linked_text(result["answer"], result, key)
    if result["steps"]:
        st.markdown("#### Действия и варианты")
        for i, step in enumerate(result["steps"], 1):
            linked_text(f"{i}. {step}", result, key)
    for message in result["conflicts"] + result["missing_information"]:
        st.warning(message)
    for message in result.get("warnings", []):
        st.caption(str(message))
    if result["sources"]:
        st.markdown("#### Источники и доказательства")
    for i, source in enumerate(result["sources"], 1):
        st.markdown(f'<div id="{key}-s{i}"></div>', unsafe_allow_html=True)
        with st.expander(f"[{i}] {source['document_title']}", expanded=settings["sources_open"]):
            st.caption(source.get("locator") or "Локатор не передан")
            st.text(source["excerpt"])
            if source.get("quotes"):
                st.caption("Цитаты в ответе")
                for quote in source["quotes"]:
                    st.text(quote)
            copy_button(source["excerpt"], "Скопировать цитату")
            if settings["advanced"]:
                metadata = {k: v for k, v in source.items() if k != "excerpt" and v is not None}
                st.json(metadata, expanded=False)
            if source.get("url") and valid_url(source["url"]):
                st.link_button("Открыть источник", source["url"])
            elif st.checkbox("Проверить наличие оригинала", key=f"{key}-file{i}"):
                path = local_document(source)
                if path:
                    with path.open("rb") as original:
                        st.download_button("Скачать оригинал", original, file_name=source["document_title"],
                                           key=f"{key}-download{i}")
                else:
                    st.caption("Оригинал этой редакции недоступен.")
    text = export_text(turn["question"], result)
    a, b, c = st.columns(3)
    with a:
        copy_button(text)
    with b:
        st.download_button("Экспорт Markdown", text, "answer.md", "text/markdown", key="md"+key)
    with c:
        st.download_button("Экспорт TXT", text, "answer.txt", "text/plain", key="txt"+key)
    if settings["advanced"]:
        meta = result["metadata"]
        st.caption(f"Время запроса {meta.get('latency_ms', '—')} мс · Поиск {meta.get('retrieval_ms', '—')} мс · Генерация {meta.get('generation_ms', '—')} мс")
        if meta.get("model"):
            st.caption(f"Модель {meta['model']}")
