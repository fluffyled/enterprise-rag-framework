"""Paired local evaluation of extractive, draft and verified output."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evaluate_hiring import prepare
from answering.core import generate
from answering.grounded import build_evidence, draft_answer, finalize, verify, verify_and_finalize

ENDPOINT = 'http://127.0.0.1:8091/v1/chat/completions'


def compare_exact(input_path, output_path):
    with Path(input_path).open(encoding='utf-8') as source, Path(output_path).open('x', encoding='utf-8') as output:
        for line in source:
            row = json.loads(line)
            if 'case' not in row:
                continue
            start = time.perf_counter()
            row['D'], row['exact_trace'] = verify_and_finalize(
                row['question'], row['draft'], row['evidence'], ENDPOINT, exact=True)
            row['seconds']['D'] = row['seconds']['B'] + time.perf_counter()-start
            output.write(json.dumps(row, ensure_ascii=False)+'\n')
            output.flush()
            print(row['case'], row['D']['status'], flush=True)


def main():
    if len(sys.argv) == 3:
        compare_exact(*sys.argv[1:])
        return
    _, clauses, cases = prepare()
    with Path('reports/grounded-abc-v1.jsonl').open('x', encoding='utf-8') as output:
        for case, question, expected, gold in cases:
            missing = {'removed_deadline': '3.8', 'removed_condition': '3.5'}.get(case)
            fragments = [f for key, f in clauses.items() if key != missing]
            start = time.perf_counter()
            a = generate(question, fragments, ENDPOINT)
            a_time = time.perf_counter() - start
            start = time.perf_counter()
            evidence = build_evidence(fragments)
            draft = draft_answer(question, evidence, ENDPOINT)
            b = finalize(draft, evidence)
            b_time = time.perf_counter() - start
            c, trace = verify_and_finalize(question, draft, evidence, ENDPOINT)
            row = dict(case=case, question=question, expected=expected, gold=gold, evidence=evidence,
                       A=a, B=b, C=c, draft=draft, trace=trace,
                       seconds={'A': a_time, 'B': b_time, 'C': time.perf_counter()-start})
            output.write(json.dumps(row, ensure_ascii=False) + '\n')
            output.flush()
            print(case, a['status'], b['status'], c['status'], flush=True)
        stress = [
            ('3.8', 'Каков срок размещения?', 'УРП размещает объявление о вакансии в течение 10 рабочих дней.', False),
            ('3.8', 'Каков срок размещения?', 'УРП размещает объявление о вакансии в течение двух рабочих дней.', False),
            ('3.5', 'Кто согласует записку?', 'Непосредственный руководитель всегда согласует служебную записку.', False),
            ('3.4', 'В каком формате приложить заявку?', 'Заявку прикладывают в формате PDF.', False),
            ('3.4', 'В каком формате приложить заявку?', 'Заявку прикладывают в формате Word.', True),
            ('3.8', 'Каков срок размещения?', 'УРП размещает объявление о вакансии в течение одного рабочего дня.', True),
        ]
        for number, requirement, claim, supported in stress:
            evidence = build_evidence([clauses[number]])
            item = dict(requirement=requirement, text=claim, evidence_ids=['E1'])
            finding = verify([item], evidence, ENDPOINT)[1]
            output.write(json.dumps(dict(stress=claim, expected_supported=supported, finding=finding), ensure_ascii=False)+'\n')
            output.flush()
            print('stress', finding['verdict'], supported, flush=True)


if __name__ == '__main__':
    main()
