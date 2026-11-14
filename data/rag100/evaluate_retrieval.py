#!/usr/bin/env python3
"""Evaluate document and source-unit retrieval against rag_gold_qa.jsonl.

Usage:
    python evaluate_retrieval.py rag_gold_qa.jsonl predictions.jsonl
Prediction JSONL example:
{"id":"Q001", "retrieved":[{"document_id":"D09","unit_type":"page","unit_locator":2}], "abstained":false}

Metrics are retrieval-only. Semantic correctness of arbitrary generated answers is not inferred.
"""
import argparse, collections, json

def read_jsonl(path):
 with open(path,encoding='utf-8') as f:
  return [json.loads(line) for line in f if line.strip()]

def calc(gold,preds,ks=(1,3,5,10)):
 byid={r['id']:r for r in preds};missing=sorted(set(g['id'] for g in gold)-set(byid))
 if missing: raise ValueError(f'Missing predictions for {len(missing)} IDs: {missing[:10]}')
 pos=[g for g in gold if g['answerable']];neg=[g for g in gold if not g['answerable']]
 n=len(pos);result={'samples':len(gold),'answerable':n,'unanswerable':len(neg),'document':{},'source_unit':{}}
 rank=[]; unit_rank=[]
 for g in pos:
  pred=byid[g['id']]; retr=pred.get('retrieved',[])
  gold_docs=set(g['gold_document_ids']);doc_hits=[];unit_hits=[]
  expected=g['gold_location'];typ='page' if expected['type']=='pdf_page' else 'paragraph'
  unit_value=expected[typ]
  for index,r in enumerate(retr,1):
   d=r.get('document_id') or r.get('doc_id')
   if d in gold_docs:doc_hits.append(index)
   # For documents with duplicated provisions, only the primary document's
   # exact paragraph is evaluated; alternate documents still count for doc@k.
   if d==g['gold_document_id'] and r.get('unit_type',r.get('type')) in (typ,expected['type']):
    loc=r.get('unit_locator',r.get(typ,r.get('locator')))
    if str(loc)==str(unit_value):unit_hits.append(index)
  rank.append(min(doc_hits) if doc_hits else None)
  unit_rank.append(min(unit_hits) if unit_hits else None)
 for k in ks:
  result['document'][f'Hit@{k}']=round(sum(x is not None and x<=k for x in rank)/n,4) if n else None
  result['source_unit'][f'Hit@{k}']=round(sum(x is not None and x<=k for x in unit_rank)/n,4) if n else None
 result['document']['MRR@10']=round(sum((1.0/x if x<=10 else 0.0) for x in rank if x)/n,4) if n else None
 result['source_unit']['MRR@10']=round(sum((1.0/x if x<=10 else 0.0) for x in unit_rank if x)/n,4) if n else None
 answers_provided=all('abstained' in byid[g['id']] for g in gold)
 if answers_provided:
  # This is a decision metric only, not a semantic QA metric.
  tp=sum(bool(byid[g['id']]['abstained']) for g in neg)
  tn=sum(not bool(byid[g['id']]['abstained']) for g in pos)
  result['abstention']={'specificity_on_answerable':round(tn/n,4) if n else None,
   'recall_on_unanswerable':round(tp/len(neg),4) if neg else None,
   'overall_accuracy':round((tp+tn)/len(gold),4)}
 else:
  result['abstention']='Not computed; provide a boolean "abstained" for every prediction.'
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('gold');p.add_argument('predictions');p.add_argument('--split',choices=['dev','test','all'],default='all');p.add_argument('--out')
 a=p.parse_args(); gold=read_jsonl(a.gold); predictions=read_jsonl(a.predictions)
 if a.split!='all':gold=[g for g in gold if g['split']==a.split]
 report=calc(gold,predictions)
 message=json.dumps(report,ensure_ascii=False,indent=2)
 if a.out:
  with open(a.out,'w',encoding='utf8') as f:f.write(message+'\n')
 print(message)
