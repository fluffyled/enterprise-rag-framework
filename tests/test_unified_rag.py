import json
from types import SimpleNamespace

import pytest

from answering.v2 import pipeline
from navigator import generation_service, rag_service
from navigator.evidence_adapter import adapt_evidence, validate_citation


def document(doc_id="rules.pdf", **meta):
    return SimpleNamespace(id="shared", content="Работник может подать заявку в отдел кадров.",
                           meta={"document_id": doc_id, "name": doc_id, **meta})


def test_evidence_lineage_and_identical_text():
    a = document(sha256="v1", source_span={"start": 3, "end": 49})
    b = document("copy.xlsx", locator="лист A, строка 1")
    text = "xx " + a.content
    a.meta["source_span"]["end"] = len(text)
    corpus = [{"document_id": "rules.pdf", "sha256": "v1", "text": text}]
    first, second = adapt_evidence([a, a, b], "quality", corpus)
    assert first.id != second.id
    assert first.source_spans == [(3, len(text))]
    assert second.source_spans == []
    assert first.id == adapt_evidence([a], "fast", corpus)[0].id
    with pytest.raises(ValueError):
        validate_citation(first, "обязан")


@pytest.mark.parametrize("profile,mode", [("fast", "g2"), ("quality", "g2"), ("quality", "legacy")])
def test_application_chain(tmp_path, monkeypatch, profile, mode):
    index, clauses = tmp_path / "index.json", tmp_path / "clauses.json"
    for path in (index, clauses):
        path.touch()
    (tmp_path / "snapshot.json").write_text('{"empty":false}')
    d = document()

    class Retriever:
        def search(self, question, config):
            assert config["retrieval"]["parent_expansion"] == (profile == "quality")
            return [d]

    monkeypatch.setattr(rag_service, "_resource_key", (index, tuple(
        p.stat().st_mtime_ns if p.exists() else None for p in [
            index, clauses, tmp_path / "source_documents.json", *rag_service.PROFILES.values(),
            tmp_path / "snapshot.json",
        ]
    )))
    monkeypatch.setattr(rag_service, "resources", lambda *args: (Retriever(), {}, []))

    def client(endpoint, payload, trace):
        data = json.loads(payload["messages"][1]["content"])
        schema = payload["response_format"]["schema"]["properties"]
        if "aspects" in schema:
            return {"aspects": ["Куда подать заявку?"]}
        if "facts" in schema:
            return {"facts": [{"text": d.content, "kind": "action", "modality": "permitted",
                               "alternative": "Подача в отдел кадров", "actor": "Работник",
                               "requirement_ids": ["R1"],
                               "citations": [{"evidence_id": data["evidence"][0]["id"], "quote": d.content}]}]}
        return {"verdicts": [{"id": "F1", "verdict": "supported"}],
                "missing": [], "conflict_evidence_ids": []}

    monkeypatch.setattr(generation_service, "generate_v2", lambda request, settings:
                        pipeline.generate_v2(request, settings=settings, client=client))
    monkeypatch.setattr(generation_service, "answer", lambda *_: {
        "status": "supported_quotes", "answer": [{"source": 1, "quote": d.content}], "steps": [], "conflicts": []})
    result = rag_service.ask("Куда подать заявку?", profile, mode, snapshot=tmp_path)
    assert result.status == "partial"
    assert result.summary[0]["citations"] == [result.sources[0]["id"]]
    assert result.sources[0]["quotes"] == [d.content]
    if mode == "g2":
        assert result.steps[0]["modality"] == "permitted"
        assert result.steps[0]["alternative"]


def test_llm_failure_is_error(monkeypatch):
    def offline(*args, **kwargs):
        raise TimeoutError("server timed out")

    monkeypatch.setattr(generation_service, "generate_v2", lambda request, settings:
                        pipeline.generate_v2(request, settings=settings, client=offline))
    result = generation_service.GenerationService().generate("Куда подать заявку?",
                                                            adapt_evidence([document()], "fast"), "g2")
    assert result.status == "error"
    assert len(result.diagnostics["trace"]["calls"]) == 2


def test_missing_or_empty_documents(tmp_path):
    assert rag_service.ask("Вопрос", snapshot=tmp_path).status == "error"
    (tmp_path / "snapshot.json").write_text('{"empty":true}')
    assert rag_service.ask("Вопрос", snapshot=tmp_path).status == "insufficient"
