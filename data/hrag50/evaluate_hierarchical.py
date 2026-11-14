#!/usr/bin/env python3
"""Offline hierarchical-retrieval evaluation. No LLM judge and no runtime gold access."""
import argparse
import json
from pathlib import Path


def recall(gold,pred,k):
    gold=set(gold)
    return (len(gold.intersection(pred[:k]))/len(gold)) if gold else 1.0

def full(gold,pred,k):
    return float(set(gold)<=set(pred[:k]))

def mrr(gold,pred,k=10):
    gold_set=set(gold)
    for i,p in enumerate(pred[:k]):
        if p in gold_set:
            return 1.0/(i+1)
    return 0.0

def summarize(values):
    return round(sum(values)/len(values),4) if values else None

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gold',type=Path,default=Path(__file__).with_name('hierarchical_complex_qa_50.jsonl'))
    parser.add_argument('--predictions',type=Path,required=True)
    parser.add_argument('--split',choices=['all','dev','test'],default='test')
    parser.add_argument('--out',type=Path,default=None)
    args=parser.parse_args()
    gold=[json.loads(l) for l in args.gold.read_text(encoding='utf8').splitlines() if l.strip()]
    if args.split!='all':gold=[x for x in gold if x['split']==args.split]
    pred={}
    for line in args.predictions.read_text(encoding='utf8').splitlines():
        if not line.strip():continue
        row=json.loads(line)
        if row['id'] in pred:raise ValueError(f'Duplicate prediction id {row["id"]}')
        pred[row['id']]=row
    missing=[r['id'] for r in gold if r['id'] not in pred]
    if missing:raise ValueError(f'Missing predictions for {len(missing)} questions, e.g. {missing[:5]}')
    metric_lists={}
    metrics=[]
    def add(name,v):metric_lists.setdefault(name,[]).append(float(v))
    for g in gold:
        p=pred[g['id']]
        docs=p.get('retrieved_documents',[])
        units=p.get('retrieved_source_units',[])
        clauses=p.get('retrieved_clause_ids',None)
        selected=p.get('selected_context_clause_ids',None)
        selected_units=p.get('selected_context_source_unit_ids',None)
        gdocs=g['gold_document_filenames'];gunits=g['gold_source_unit_ids'];gclauses=g['gold_clause_ids']
        entry={'id':g['id'],'category':g['category'],'split':g['split']}
        for prefix,G,P in [('document',gdocs,docs),('source_unit',gunits,units)]:
            rr=mrr(G,P,10)
            add(f'{prefix}_mrr@10',rr)
            entry[f'{prefix}_mrr@10']=round(rr,4)
        if clauses is not None:
            add('clause_mrr@10',mrr(gclauses,clauses,10))
        for k in [1,5,10]:
            for prefix,G,P in [('document',gdocs,docs),('source_unit',gunits,units)]:
                a=recall(G,P,k);b=full(G,P,k)
                add(f'{prefix}_recall@{k}',a);add(f'{prefix}_all@{k}',b)
                entry[f'{prefix}_recall@{k}']=round(a,4)
            if clauses is not None:
                a=recall(gclauses,clauses,k)
                add(f'clause_recall@{k}',a);entry[f'clause_recall@{k}']=round(a,4)
        if selected is not None:
            gold_set=set(gclauses);selected_set=set(selected)
            clause_coverage=len(gold_set & selected_set)/len(gold_set)
            add('selected_clause_coverage',clause_coverage)
            add('complete_clause_context',int(gold_set<=selected_set))
            facts_cov=[set(f['evidence_ids'])<=selected_set for f in g['required_facts']]
            fact_coverage=sum(facts_cov)/len(facts_cov)
            add('fact_evidence_coverage',fact_coverage)
            add('all_facts_supported_in_context',all(facts_cov))
            entry['selected_clause_coverage']=round(clause_coverage,4)
            entry['fact_evidence_coverage']=round(fact_coverage,4)
        if selected_units is not None:
            unit_coverage=len(set(gunits)&set(selected_units))/len(set(gunits))
            add('selected_source_unit_coverage',unit_coverage)
        # Explicitly labeled answer fact IDs, e.g. external manual/LLM judge decisions.
        # Do NOT try to score semantic correctness by string matching.
        if 'judged_correct_fact_ids' in p:
            correct=set(p['judged_correct_fact_ids'])
            required={f['fact_id'] for f in g['required_facts']}
            if not correct<=required:raise ValueError(f'Unknown fact ids for {g["id"]}: {correct-required}')
            add('judged_answer_fact_recall',len(correct)/len(required))
            add('judged_complete_answer',required<=correct)
        metrics.append(entry)
    result={'split':args.split,'questions':len(gold),'metrics':{k:summarize(v) for k,v in sorted(metric_lists.items())},
            'per_question':metrics,
            'limitations':['Clause metrics require explicit retrieved_clause_ids; cannot be inferred merely from page hits.',
            'Semantic answer correctness and false steps need manual/judge annotations.',
            'All complex50 questions are answerable; use a separate negative-set for abstention.']}
    serialized=json.dumps(result,ensure_ascii=False,indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(serialized,encoding='utf8')
    print(json.dumps({k:v for k,v in result.items() if k!='per_question'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
