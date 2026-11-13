from answering import grounded
from answering.contracts import Fragment


def evidence():
    return grounded.build_evidence([
        Fragment('1', 'doc', 'Заявку прикладывают в формате Word.', 'Регламент', 'п. 1')
    ])


def test_wrong_number_is_rejected_without_model():
    items = [{'requirement': 'Какой срок?', 'text': 'Подать за 10 дней.', 'evidence_ids': ['E1']}]
    findings = grounded.verify(items, evidence(), 'unused')
    assert findings[1]['verdict'] == 'unsupported'
    assert grounded.finalize(items, evidence(), findings) == {
        'status': 'insufficient', 'answer': [], 'missing': ['Какой срок?']
    }


def test_invalid_verifier_quote_and_omitted_verdict_do_not_pass(monkeypatch):
    item = {'requirement': 'Какой формат?', 'text': 'Заявку прикладывают в формате Word.', 'evidence_ids': ['E1']}
    monkeypatch.setattr(grounded, 'ask', lambda *args: [
        {'id': 1, 'verdict': 'supported', 'quote': 'Придуманная цитата', 'evidence_id': 'E1'}
    ])
    items = [item, dict(item, requirement='Кто подаёт?')]
    findings = grounded.verify(items, evidence(), 'unused')
    assert grounded.finalize(items, evidence(), findings)['answer'] == []
    assert all(review['verdict'] == 'unsupported' for review in findings.values())


def test_extractive_fallback_cannot_be_called_complete():
    result = {'status': 'insufficient', 'answer': [], 'missing': ['Кто согласует?']}
    assert grounded.fallback_answer(result, {'status': 'answered', 'answer': [{}]})['status'] == 'partial'
