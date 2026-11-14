"""Классификация типа вопроса для адаптивного выбора стратегии контекста.

Простой интерпретируемый классификатор без LLM: признаки — число подзадач
правиловой декомпозиции, маркеры перечислений, ссылки на типы документов и даты.

Типы:
- single_fact — один факт из одного документа (стратегия top_k);
- multi_requirement — несколько условий/требований (protected coverage);
- multi_document — сведения из нескольких документов (plain coverage, шире охват);
- uncertain — сигналы слабые или противоречивые (консервативный top_k).

Гипотезы соответствия тип→стратегия проверяются экспериментально (этап 3),
модуль не использует gold-разметку.
"""

import re

_DOC_TYPE_RE = re.compile(r"\b(приказ|регламент|инструкци\w+|положени\w+|договор\w*|смет\w+|бюджет\w*|приложени\w+|распоряжени\w+|contract\w*|agreement\w*|polic\w+|clause\w*|exhibit\w*|schedule\w*|section\w*)\b", re.IGNORECASE)
_ENUM_RE = re.compile(r"\b(перечислите|назовите|укажите|какие|каких|сколько|list|name|what are|which|how many)\b", re.IGNORECASE)
_LIST_RE = re.compile(r"\s+(?:и|а также|либо|или|and|or|as well as)\s+|,", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

STRATEGY_BY_TYPE = {
    "single_fact": "top_k",
    "multi_requirement": "protected_coverage",
    "multi_document": "coverage",
    "uncertain": "top_k",
}


def classify_question(question, subtasks=None):
    text = question or ""
    lowered = text.lower()
    list_markers = len(_LIST_RE.findall(lowered))
    enum_cue = bool(_ENUM_RE.search(text))
    subtask_count = len(subtasks or [])
    doc_types = {match.group(1).lower() for match in _DOC_TYPE_RE.finditer(text)}
    years = set(_YEAR_RE.findall(text))

    multi_requirement = subtask_count >= 2 or (enum_cue and list_markers >= 2)
    multi_document = len(doc_types) >= 2 or (len(doc_types) >= 1 and len(years) >= 2 and list_markers >= 1)

    signals = {
        "subtasks": subtask_count,
        "list_markers": list_markers,
        "enum_cue": enum_cue,
        "doc_types": sorted(doc_types),
        "years": sorted(years),
    }
    if multi_requirement and multi_document:
        return {"type": "multi_document", "confidence": 0.6, "signals": signals, "reason": "несколько требований и несколько типов документов/дат"}
    if multi_requirement:
        confidence = 0.8 if subtask_count >= 2 else 0.6
        return {"type": "multi_requirement", "confidence": confidence, "signals": signals, "reason": f"подзадач: {subtask_count}, маркеров перечисления: {list_markers}"}
    if multi_document:
        return {"type": "multi_document", "confidence": 0.6, "signals": signals, "reason": f"типов документов: {len(doc_types)}, дат: {len(years)}"}
    if list_markers >= 2:
        return {"type": "uncertain", "confidence": 0.4, "signals": signals, "reason": "маркеры перечисления без подтверждённых требований"}
    return {"type": "single_fact", "confidence": 0.8, "signals": signals, "reason": "признаков составного вопроса нет"}


def choose_strategy(question, subtasks=None):
    decision = classify_question(question, subtasks)
    decision["strategy"] = STRATEGY_BY_TYPE[decision["type"]]
    return decision
