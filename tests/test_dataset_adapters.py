from navigator.evaluation.datasets.legalbench import parse_legalbench
from navigator.evaluation.datasets.multidoc2dial import parse_multidoc2dial


def test_multidoc_history_and_target_answer_separation():
    documents = {"doc_data": {"dmv": {"doc": {
        "title": "Document", "doc_text": "0123456789abcdefghij",
        "spans": {"1": {"id_sp": "1", "start_sp": 2, "end_sp": 8}},
    }}}}
    dialogues = {"dial_data": {"dmv": [{"dial_id": "d", "turns": [
        {"turn_id": 1, "role": "user", "da": "query", "utterance": "first", "references": []},
        {"turn_id": 2, "role": "agent", "da": "respond_solution", "utterance": "first answer", "references": [{"id_sp": "1", "doc_id": "doc"}]},
        {"turn_id": 3, "role": "user", "da": "query", "utterance": "second", "references": []},
        {"turn_id": 4, "role": "agent", "da": "respond_solution", "utterance": "SECRET TARGET", "references": [{"id_sp": "1", "doc_id": "doc"}]},
    ]}]}}
    dataset = parse_multidoc2dial(documents, dialogues)
    assert len(dataset["queries"]) == 2
    current = dataset["queries"][1]
    assert "first answer" in current["question"]
    assert "SECRET TARGET" not in current["question"]
    assert current["evidence_groups"][0]["alternatives"][0] == {"document_id": "doc", "start": 2, "end": 8, "text": "234567"}
    assert dataset["metadata"]["target_agent_answer_in_query"] is False


def test_multidoc_does_not_label_dialogue_as_multi_document():
    documents = {"doc_data": {"dmv": {"doc": {"title": "D", "doc_text": "abcdef", "spans": {"1": {"id_sp": "1", "start_sp": 0, "end_sp": 3}}}}}}
    dialogues = {"dial_data": {"dmv": [{"dial_id": "d", "turns": [
        {"turn_id": 1, "role": "user", "utterance": "q", "references": []},
        {"turn_id": 2, "role": "agent", "da": "respond_solution", "utterance": "a", "references": [{"id_sp": "1", "doc_id": "doc"}]},
    ]}]}}
    case = parse_multidoc2dial(documents, dialogues)["queries"][0]
    assert case["gold_document_ids"] == ["doc"]
    assert len(case["evidence_groups"]) == 1


def test_legalbench_precise_spans_and_record_counts():
    benchmark = {"tests": [{"query": "q", "snippets": [{"file_path": "a.txt", "span": [2, 5]}], "tags": ["mini"]}]}
    dataset = parse_legalbench(benchmark, {"a.txt": "0123456789"}, "mini")
    case = dataset["queries"][0]
    assert case["gold_document_ids"] == ["a.txt"]
    assert case["evidence_groups"][0]["alternatives"][0]["start"] == 2
    assert dataset["metadata"]["source_record_count"] == 1
    assert dataset["chunks"][0]["meta"]["source_span"]["start"] == 0
