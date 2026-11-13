"""Local paired development pilot. Regulation text and generated answers stay in reports/."""
import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from answering.contracts import Fragment
from answering.core import generate
from answering.decomposition import generate_by_parts


def prepare():
    snapshot = ROOT / '.cache/llm-experiments/2026-11-12/sevsese/data/eval_cases.json'
    raw = (snapshot if snapshot.exists() else ROOT / 'data/eval_cases.json').read_bytes()
    seeds = {row['id']: row for row in json.loads(raw)}
    title, = seeds['steps']['expected_docs']
    path = ROOT / 'data/extracted' / (title + '.txt')
    source = path.read_text(encoding='utf-8')
    starts = list(re.finditer(r'^3\.(?:[1-9]|10)\.\s+', source, re.M))
    clauses = {}
    for left, right in zip(starts, starts[1:]):
        number = left.group().strip().rstrip('.')
        body = ' '.join(source[left.end():right.start()].split())
        clauses[number] = Fragment(number, hashlib.sha256(source.encode()).hexdigest(), body,
                                   title, f'п. {number}', complete=True)
    initiator = ('3.1', 'является руководитель подразделения')
    duration = ('3.8', 'в течение одного рабочего дня')
    fields = ('3.2', 'должны быть заполнены')
    submit = ('3.4', 'с приложением заявки в формате Word')
    conditional = ('3.5', 'непосредственным руководителем (если заявку отправляет ответственное лицо)')
    upper = ('3.5', 'вышестоящим руководителем, а также курирующим проректором/директором')
    rows = [
        ('single', seeds['single']['question'], 'answered', [initiator]),
        ('paraphrase', seeds['paraphrase']['question'], 'answered', [duration]),
        ('steps', seeds['steps']['question'], 'answered', [fields, submit, conditional, upper]),
        ('initiator_variant', 'Чья роль по регламенту — начать подбор в своё подразделение?', 'answered', [initiator]),
        ('deadline_variant', 'Какой срок установлен УРП для размещения объявления о вакансии?', 'answered', [duration]),
        ('delegate_condition', 'При каком условии для служебной записки требуется согласование непосредственного руководителя?', 'answered', [conditional]),
        ('remaining_approvals', 'Какие согласования названы в п. 3.5 помимо непосредственного руководителя?', 'answered', [upper]),
        ('several_slots', 'Кому направить служебную записку, в каком формате приложить заявку и кто её согласует?', 'answered', [('3.4', 'директору по общим вопросам'), submit, conditional, upper]),
        ('removed_deadline', seeds['paraphrase']['question'], 'insufficient', []),
        ('removed_condition', 'При каком условии нужно согласование непосредственного руководителя и в каком формате прикладывают заявку?', 'partial', [submit]),
    ]
    return raw, clauses, rows


# Human-written decomposition for two diagnostic questions. No gold clause IDs
# or expected strings are passed to the generator.
SUBQUESTIONS = {
    'steps': [
        'Какие поля заявки на подбор нужно заполнить?',
        'Как отправить служебную записку и в каком формате приложить заявку?',
        'Кто согласует записку и при каком условии нужен непосредственный руководитель?',
    ],
    'several_slots': [
        'Кому направить служебную записку и в каком формате приложить заявку?',
        'Кто согласует записку и при каком условии нужен непосредственный руководитель?',
    ],
}


def run_decomposition(cases, clauses, output):
    for case_id, question, _, gold in cases:
        if case_id not in SUBQUESTIONS:
            continue
        start = time.perf_counter()
        answers = [generate(q, list(clauses.values()), 'http://127.0.0.1:8091/v1/chat/completions',
                            whole_clauses=True) for q in SUBQUESTIONS[case_id]]
        quotes = [quote for answer in answers for quote in answer['answer'] + answer['steps']]
        covered = [any(q['fragment_id'] == number and anchor in q['quote'] for q in quotes)
                   for number, anchor in gold]
        output.write(json.dumps(dict(case=case_id, question=question, subquestions=SUBQUESTIONS[case_id],
                                     results=answers, gold=gold, covered=covered,
                                     seconds=round(time.perf_counter() - start, 3)), ensure_ascii=False) + '\n')
        print(case_id, 'manual decomposition', f'{sum(covered)}/{len(gold)}', flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path, help='New file under reports/')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--decompose', action='store_true')
    modes.add_argument('--automatic', action='store_true')
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT / 'reports'):
        parser.error('Use a new file under reports/')
    raw, clauses, cases = prepare()
    if args.decompose:
        with args.output.open('x', encoding='utf-8') as output:
            run_decomposition(cases, clauses, output)
        return
    arms = ('automatic',) if args.automatic else ('sentences', 'clauses')
    totals = {arm: Counter() for arm in arms}
    with args.output.open('x', encoding='utf-8') as output:
        output.write(json.dumps({'seed_sha256': hashlib.sha256(raw).hexdigest(),
                                 'family': 'hiring', 'split': 'dev', 'cases': len(cases)}) + '\n')
        for case_id, question, expected, gold in cases:
            missing = {'removed_deadline': '3.8', 'removed_condition': '3.5'}.get(case_id)
            fragments = [clause for number, clause in clauses.items() if number != missing]
            for number, anchor in gold:
                assert anchor in clauses[number].text and number != missing, (case_id, anchor)
            for arm in totals:
                start = time.perf_counter()
                endpoint = 'http://127.0.0.1:8091/v1/chat/completions'
                if arm == 'automatic':
                    result = generate_by_parts(question, fragments, endpoint)
                    selected = [part['result'] for part in result['parts']]
                else:
                    result = generate(question, fragments, endpoint, whole_clauses=arm == 'clauses')
                    selected = [result]
                quotes = [quote for item in selected for quote in item['answer'] + item['steps']]
                covered = [any(q['fragment_id'] == number and anchor in q['quote'] for q in quotes)
                           for number, anchor in gold]
                status_ok = result['status'] == expected
                totals[arm].update(status_correct=int(status_ok), anchors_covered=sum(covered),
                                   anchors_total=len(gold), all_required=sum(covered) == len(gold) and bool(gold),
                                   false_complete=result['status'] == 'answered' and (expected != 'answered' or not all(covered)),
                                   errors=result['status'] == 'error')
                output.write(json.dumps(dict(case=case_id, question=question, arm=arm, expected=expected,
                                             gold=gold, covered=covered, result=result,
                                             seconds=round(time.perf_counter() - start, 3)), ensure_ascii=False) + '\n')
                output.flush()
                print(case_id, arm, result['status'], f'{sum(covered)}/{len(gold)}', flush=True)
        output.write(json.dumps({'totals': totals}) + '\n')
    print(json.dumps(totals, indent=2))


if __name__ == '__main__':
    main()
