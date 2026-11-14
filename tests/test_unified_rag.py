import json
from types import SimpleNamespace

import pytest

from answering.v2 import pipeline
from navigator import generation_service, rag_service
from navigator.evidence_adapter import adapt_evidence, validate_citation
from navigator.answer import selected_quotes, sentence_options


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
        rag_service.artifact_stamp(p) for p in [
            index, clauses, tmp_path / "source_documents.json", *rag_service.PROFILES.values(),
            tmp_path / "snapshot.json",
        ]
    ) + (rag_service.fingerprint(tmp_path / "snapshot.json"),)))
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
    assert result.diagnostics["transport_error"]
    assert len(result.diagnostics["trace"]["calls"]) == 2


def test_legacy_rejects_missing_fields_and_preserves_steps():
    docs = [document()]
    options = sentence_options(docs)
    with pytest.raises(ValueError):
        selected_quotes({}, options, docs)
    result = selected_quotes({"insufficient": False, "answer_ids": [], "step_ids": [1],
                              "conflict_pairs": []}, options, docs)
    assert result["status"] == "supported_quotes"
    assert result["steps"][0]["quote"] == docs[0].content


def test_evidence_batches_bound_escaped_json_and_preserve_order():
    from answering.v2.contracts import Evidence

    evidence = [Evidence(id="Z", document_id="d", full_text='"\\' * 100),
                Evidence(id="A", document_id="d", full_text="строка")]
    batches = pipeline.evidence_batches(evidence, 140, "map")
    assert all(len(json.dumps(batch, ensure_ascii=False)) <= 140 for batch in batches)
    rows = [row for batch in batches for row in batch]
    assert rows[-1]["id"] == "A"
    assert "".join(row["text"] for row in rows if row["id"] == "Z") == evidence[0].full_text


@pytest.mark.parametrize("item,exception", [
    ("при сниженных накладных", "кроме договоров с лимитом от грантодателя"),
    ("без аванса", "кроме договоров по итогам конкурса"),
])
def test_visible_summary_preserves_list_scope(monkeypatch, item, exception):
    from answering.v2.contracts import Evidence
    from ui import services

    intro = "4. Запрет действует для договоров, заключённых после утверждения регламента:"
    bullet = f"- {item}, {exception};"
    source = Evidence(id="E1", document_id="rules", document_title="Правила",
                      full_text=f"{intro}\n{bullet}\n- при задолженности.")

    def client(endpoint, payload, trace):
        data = json.loads(payload["messages"][1]["content"])
        properties = payload["response_format"]["schema"]["properties"]
        if "aspects" in properties:
            return {"aspects": [item]}
        if "verdicts" in properties:
            return {"verdicts": [{"id": fact["id"], "verdict": "unsupported"} for fact in data["facts"]],
                    "missing": [], "conflict_evidence_ids": []}
        return {"facts": [{"text": f"Запрет {item}", "kind": "action", "requirement_ids": ["R1"],
                           "citations": [{"evidence_id": "E1", "quote": item}]}]}

    monkeypatch.setattr(generation_service, "generate_v2", lambda request, settings:
                        pipeline.generate_v2(request, settings=settings, client=client))
    result = generation_service.GenerationService().generate(item, [source], "g2")
    monkeypatch.setattr(rag_service, "ask", lambda *args, **kwargs: result)
    visible = services.connected({"question": item})
    assert visible["status"] == "partial"
    assert intro in visible["answer"] and bullet in visible["answer"]
    assert intro in visible["sources"][0]["quotes"] and bullet in visible["sources"][0]["quotes"]


def test_joint_claim_uses_both_batches():
    from answering.v2.contracts import AnswerInputV1, Evidence

    evidence = [Evidence(id="E1", document_id="rules", full_text="Ответственный — бухгалтер. " + "а" * 100),
                Evidence(id="E2", document_id="rules", full_text="Срок — три дня. " + "б" * 100)]

    def fact(ids):
        return {"text": " и ".join(evidence[i].full_text.split(".")[0] for i in ids),
                "kind": "other", "requirement_ids": ["R1"],
                "citations": [{"evidence_id": evidence[i].id, "quote": evidence[i].full_text.split(".")[0]} for i in ids]}

    def client(endpoint, payload, trace):
        data = json.loads(payload["messages"][1]["content"])
        if "facts" in data:
            return {"verdicts": [{"id": f["id"], "verdict": "supported"} for f in data["facts"]],
                    "missing": [], "conflict_evidence_ids": []}
        ids = [int(row["id"][1:]) - 1 for row in data["evidence"]]
        return {"facts": [fact(ids)]}

    settings = pipeline.Settings(input_chars=250, scoped_summary=True, repair_attempts=0, fail_on_batch_error=True)
    result = pipeline.generate_v2(AnswerInputV1(question="Кто и в какой срок?", evidence=evidence),
                                  settings=settings, client=client)
    assert result.verification.passed
    assert any({c.evidence_id for c in fact.citations} == {"E1", "E2"} for fact in result.claims)


def test_adaptive_strategy_counts_distinct_full_years():
    from navigator.adaptive_strategy import classify_question

    result = classify_question("Сравните регламент и приказ за 2024 и 2025 годы")
    assert result["signals"]["years"] == ["2024", "2025"]


def test_late_review_connection_error_keeps_verified_facts():
    from answering.v2.contracts import AnswerInputV1, Evidence

    evidence = [Evidence(id=f"E{i}", document_id="rules", full_text=f"Правило {i}. " + "а" * 125)
                for i in (1, 2)]

    def client(endpoint, payload, trace):
        data = json.loads(payload["messages"][1]["content"])
        row = data["evidence"][0]
        if "facts" in data:
            if row["id"] == "E2":
                raise TimeoutError("connection lost")
            return {"verdicts": [{"id": data["facts"][0]["id"], "verdict": "supported"}],
                    "missing": [], "conflict_evidence_ids": []}
        quote = row["text"].split(".")[0]
        return {"facts": [{"text": quote, "kind": "other", "requirement_ids": ["R1"],
                           "citations": [{"evidence_id": row["id"], "quote": quote}]}]}

    request = AnswerInputV1(question="Какое правило?", evidence=evidence)
    settings = pipeline.Settings(input_chars=250, scoped_summary=True, repair_attempts=0, fail_on_batch_error=True)
    result = pipeline.generate_v2(request, settings=settings, client=client)
    assert result.status == "partial"
    assert result.summary.text == "Правило 1"
    assert result.trace["transport_error"]


def test_missing_or_empty_documents(tmp_path):
    assert rag_service.ask("Вопрос", snapshot=tmp_path).status == "error"
    (tmp_path / "snapshot.json").write_text('{"empty":true}')
    assert rag_service.ask("Вопрос", snapshot=tmp_path).status == "insufficient"
