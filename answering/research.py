"""Generation strategies over an already retrieved list of Haystack documents."""
from navigator.answer import answer
from navigator.verified_answer import verified_answer

from .v2 import AnswerInputV1
from .v2.pipeline import Settings, generate_v2


MODES = {
    "G1": Settings(extraction="global", verify=False, input_chars=4400, direct=True),
    "G2": Settings(verify=False),
    "G3": Settings(verify=False, plan_requirements=True),
    "G4": Settings(verify=True, plan_requirements=True),
}


def freeze_documents(question, documents):
    evidence = []
    for document in documents:
        meta = document.meta
        span = meta.get("source_span") or {}
        start, end = span.get("start"), span.get("end")
        evidence.append({
            "id": document.id,
            "document_id": meta.get("document_id") or meta.get("relative_path") or meta.get("name") or document.id,
            "document_title": meta.get("name"),
            "node_id": meta.get("clause_id"),
            "full_text": document.content,
            "locator": str(meta.get("clause_number") or meta.get("locator") or ""),
            "source_spans": [[start, end]] if type(start) is int and type(end) is int and 0 <= start < end else [],
            "metadata": {"page": meta.get("page")},
        })
    return AnswerInputV1(question=question, evidence=evidence)


def generate_answer(question, documents, endpoint, mode, **kwargs):
    if mode == "G0":
        return answer(question, documents, endpoint)
    if mode == "G0-H5":
        return verified_answer(question, documents, endpoint)
    settings = kwargs.pop("settings", MODES[mode])
    request = freeze_documents(question, documents)
    return generate_v2(request, endpoint=endpoint, settings=settings, **kwargs).model_dump()
