from haystack import Document

from answering.research import freeze_documents
from answering.v2.pipeline import Settings, generate_v2


def test_truncated_retry_and_source_provenance():
    document = Document(id="clause-1", content="Заявку подают за 5 рабочих дней.", meta={
        "document_id": "regulation", "clause_number": "2.1", "page": 3,
        "source_span": {"start": 5, "end": 36},
    })
    request = freeze_documents("Когда подают заявку?", [document])
    assert request.evidence[0].source_spans == [(5, 36)]
    assert request.evidence[0].metadata["page"] == 3
    attempts = []

    def client(endpoint, payload, *, trace):
        attempts.append(payload["max_tokens"])
        if len(attempts) == 1:
            trace.update(finish_reason="length", usage={"prompt_tokens": 800}, raw="{")
            raise ValueError("Ответ модели обрезан")
        return {"facts": [{
            "text": "Заявку подают за 5 рабочих дней.", "kind": "deadline",
            "requirement_ids": ["R1"],
            "citations": [{"evidence_id": "clause-1", "quote": document.content}],
        }]}

    response = generate_v2(request, client=client, settings=Settings(verify=False))
    assert attempts == [1250, 2000]
    assert response.status == "answered"
    assert response.trace["calls"][0]["raw"] == "{"
    assert response.trace["calls"][1]["attempt"] == 2
    assert response.claims[0].citations[0].evidence_id == "clause-1"


def test_failed_retries_are_technical_error():
    request = freeze_documents("Когда подают заявку?", [
        Document(id="clause-1", content="За 5 рабочих дней."),
    ])

    def client(endpoint, payload, *, trace):
        return {"facts": None}

    response = generate_v2(request, client=client, settings=Settings(verify=False))
    assert response.status == "error"
    assert len(response.trace["calls"]) == 2


def test_model_reuses_http_connection(monkeypatch):
    from answering import core
    from io import BytesIO
    from types import SimpleNamespace

    created = []

    class Connection:
        def __init__(self, host, port, timeout):
            self.host, self.port = host, port
            self.calls = []
            created.append(self)

        def request(self, method, path, **kwargs):
            self.calls.append((method, path))

        def getresponse(self):
            response = BytesIO(b'{"choices":[{"message":{"content":"{}"}}]}')
            response.status = 200
            return response

        def close(self):
            pass

    monkeypatch.setattr(core, "_connection", SimpleNamespace())
    monkeypatch.setattr(core, "LocalModelConnection", Connection)
    endpoint = "http://127.0.0.1:8080/v1/chat/completions"
    assert core.request_selection(endpoint, {}) == core.request_selection(endpoint, {}) == {}
    assert len(created) == 1
    assert created[0].calls == [("POST", "/v1/chat/completions")] * 2
