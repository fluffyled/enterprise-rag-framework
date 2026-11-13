"""Reusable response presentation; source text is never executed as HTML."""
import html
import json
import re
import streamlit as st
import streamlit.components.v1 as components
from ui.storage import valid_url

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


def answer_view(turn, settings):
    result, key = turn["result"], turn["id"]
    st.caption(result["metadata"].get("mode", "") + " · " + LABELS[result["status"]])
    status = result["status"]
    if status == "error":
        st.error(result.get("error", "Ошибка сервиса"))
    elif status == "insufficient":
        st.info("В доступных документах недостаточно информации для подтвержденного ответа.")
    elif status == "partial":
        st.warning("Подтверждена только часть ответа. Не используйте её как полную инструкцию.")
    elif status == "conflict":
        st.warning("Возможное противоречие. Требуется проверка связанных источников.")
    if result["answer"]:
        linked_text(result["answer"], result, key)
    if result["steps"]:
        st.markdown("#### Порядок действий")
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
            copy_button(source["excerpt"], "Скопировать цитату")
            if settings["advanced"]:
                metadata = {k: v for k, v in source.items() if k != "excerpt" and v is not None}
                st.json(metadata, expanded=False)
            if source.get("url") and valid_url(source["url"]):
                st.link_button("Открыть источник", source["url"])
    text = export_text(turn["question"], result)
    a, b, c = st.columns(3)
    with a:
        copy_button(text)
    with b:
        st.download_button("Экспорт Markdown", text, "answer.md", "text/markdown", key="md"+key)
    with c:
        st.download_button("Экспорт TXT", text, "answer.txt", "text/plain", key="txt"+key)
    if settings["advanced"]:
        st.caption(f"Время запроса: {result['metadata'].get('latency_ms', '—')} мс · Источников: {len(result['sources'])}. В демо это время чтения примера, не инференса.")
