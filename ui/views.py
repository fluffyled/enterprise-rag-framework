"""Reusable response presentation; source text is never executed as HTML."""
import html
import re
from pathlib import Path
import streamlit as st
from navigator.corpus import fingerprint
from navigator.settings import DATA
from ui.storage import STORE, valid_url

LABELS = {"answered": "Ответ по документам", "partial": "Частичный ответ", "insufficient": "Недостаточно информации", "conflict": "Возможное противоречие", "error": "Техническая ошибка"}
PDF_BULLETS = str.maketrans({"\uf02d": "•", "\uf0b7": "•"})


def additional_answer(result):
    """Keep summary information that is absent from the displayed steps."""
    if not result["steps"]:
        return result["answer"]
    steps = [step.split(" · ") for step in result["steps"]]
    return "\n\n".join(part for part in result["answer"].split("\n\n")
                      if part.strip() and not any(part.strip() == segment.strip()
                                                  for step in steps for segment in step))


def export_text(question, result):
    lines = [f"# {question}", "", f"Режим: {result['metadata'].get('mode', '')}", f"Статус: {LABELS[result['status']]}", ""]
    lines += [f"{i}. {step}" for i, step in enumerate(result["steps"], 1)]
    if extra := additional_answer(result):
        lines += ["", extra]
    lines += result["conflicts"] + result["missing_information"]
    if result.get("error"):
        lines.append(result["error"])
    for i, s in enumerate(result["sources"], 1):
        lines += ["", f"[{i}] {s['document_title']} — {s.get('locator', '')}", s["excerpt"]]
    return "\n".join(lines).translate(PDF_BULLETS)


def linked_text(text, result, prefix):
    escaped = html.escape(text.translate(PDF_BULLETS))
    def link(match):
        number = int(match.group(1))
        if 1 <= number <= len(result["sources"]):
            return f'<a href="#{prefix}-s{number}" target="_self">{match.group(0)}</a>'
        return match.group(0)
    pattern = r"\[(\d+)\]" if result["metadata"].get("mode") == "Демонстрационный" else r"\[источник (\d+)\]"
    st.markdown('<div class="answer-text">' + re.sub(pattern, link, escaped).replace('\n', '<br>') + '</div>', unsafe_allow_html=True)


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
    if result["steps"]:
        st.markdown("#### Действия и варианты")
        for i, step in enumerate(result["steps"], 1):
            linked_text(f"{i}. {step}", result, key)
    if extra := additional_answer(result):
        linked_text(extra, result, key)
    if status == "partial":
        st.warning("Ответ может быть неполным. Проверьте условия и исключения в источниках.")
    elif status == "conflict":
        st.warning("Возможное противоречие. Требуется проверка связанных источников.")
    for message in result["conflicts"]:
        linked_text(message, result, key)
    for message in result["missing_information"]:
        st.warning(message)
    for message in result.get("warnings", []):
        st.caption(str(message))
    if result["sources"]:
        st.markdown("#### Источники и доказательства")
    for i, source in enumerate(result["sources"], 1):
        st.markdown(f'<div id="{key}-s{i}"></div>', unsafe_allow_html=True)
        with st.expander(f"[{i}] {source['document_title']}", expanded=settings["sources_open"]):
            st.caption(source.get("locator") or "Локатор не передан")
            st.code(source["excerpt"], language=None, wrap_lines=True)
            if source.get("quotes"):
                st.caption("Цитаты в ответе")
                for quote in source["quotes"]:
                    st.code(quote, language=None, wrap_lines=True)
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
    if status != "error":
        with st.expander("Экспорт ответа"):
            text = export_text(turn["question"], result)
            st.download_button("Скачать Markdown", text, "answer.md", "text/markdown", key="md"+key)
            st.download_button("Скачать TXT", text, "answer.txt", "text/plain", key="txt"+key)
    if settings["advanced"]:
        meta = result["metadata"]
        timings = [f"{label} {meta[field] / 1000:.2f} с" for field, label in
                   (("latency_ms", "Всего"), ("retrieval_ms", "Поиск"), ("generation_ms", "Генерация"))
                   if isinstance(meta.get(field), (int, float))]
        if timings:
            st.caption(" · ".join(timings))
        if meta.get("transport_detail") or (status == "error" and meta.get("review_issues")):
            with st.expander("Подробности ошибки"):
                st.text(meta.get("transport_detail") or str(meta["review_issues"][-1]))
        if meta.get("model"):
            st.caption(f"Модель {meta['model']}")
