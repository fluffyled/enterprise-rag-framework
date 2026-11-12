"""Transparent exact metrics + explicitly labelled same-model semantic estimates."""
import json,csv,hashlib,re,datetime,bisect,collections,math
from pathlib import Path
import numpy as np
from jsonschema import validate
ROOT=Path(__file__).parent
ARMS={'A0':'A0_baseline','A1':'A1','A2':'A2_v2','A3':'A3_procedure_v3','A4':'A4_v2'}
def read(p):return json.loads(p.read_text(encoding='utf8'))
def ratio(a,b):return float(a/b) if b else None

def rows(split='test'):
 cs=read(ROOT/(split+'_cases.json'));ann=read(ROOT/'procedure_annotations.json')['cases'];groups=read(ROOT/'document_groups.json')['case_to_group'];out=[]
 samples=[]
 for line in (ROOT/'resource_samples.jsonl').open(encoding='utf8'):
  try:samples.append(json.loads(line))
  except ValueError:pass
 times=[x['time'] for x in samples]
 for a,aid in ARMS.items():
  journals=collections.defaultdict(list);jp=ROOT/'http_journal'/(split+'_'+aid+'.jsonl')
  if jp.exists():
   for line in jp.open(encoding='utf8'):
    try:x=json.loads(line);journals[x['case_id']].append(x)
    except ValueError:pass
  for c in cs:
   p=ROOT/'runs'/split/aid/(c['id']+'.json')
   if not p.exists():continue
   r=read(p);calls=r.get('calls',[]) or journals.get(c['id'],[]);json_ok=None
   if any(x.get('response',{}).get('choices') for x in calls):
    json_ok=1
    for call in calls:
     if not call.get('response',{}).get('choices'):continue
     try:
      parsed=json.loads(call['response']['choices'][0]['message']['content']);validate(parsed,call['request']['response_format']['schema'])
     except Exception:json_ok=0
   pred=set(d for kind in ['claims','actions'] for x in r.get(kind,[]) for d in x['doc_ids']);gold=set(c['gold_doc_ids'])
   row=dict(case_id=c['id'],dataset=c['dataset'],split=split,arm=a,arm_id=aid,group=groups.get(c['id'],c['group_id']),answerable=c['answerable'],status=r['status'],seconds=r['seconds'],json_valid=json_ok,contract_valid=int(r['valid']),id_correct=len(pred&gold),id_pred=len(pred),id_gold=len(gold),good=int(c['answerable']),ood=int(not c['answerable']),false_refusal=int(c['answerable'] and r['status']=='insufficient'),abstain_tp=int(not c['answerable'] and r['status']=='insufficient'),abstain_pred=int(r['status']=='insufficient'),false_answer=int(not c['answerable'] and r['status'] in ['answered','partial']),partial=int(r['status']=='partial'),error=int(r['status']=='error'),calls=len(calls),prompt_tokens=sum(x['response'].get('usage',{}).get('prompt_tokens',0) for x in calls),output_tokens=sum(x['response'].get('usage',{}).get('completion_tokens',0) for x in calls))
   text=' '.join(x['text'] for k in ['claims','actions'] for x in r.get(k,[]));letters=re.findall(r'[^\W\d_]',text);row['output_chars']=len(text);row['russian_script_share']=ratio(len(re.findall('[А-Яа-яЁё]',text)),len(letters))
   if 'started_utc' in r:
    lo=datetime.datetime.fromisoformat(r['started_utc']).timestamp();hi=datetime.datetime.fromisoformat(r['ended_utc']).timestamp();window=samples[bisect.bisect_left(times,lo):bisect.bisect_right(times,hi)]
    if window:row.update(peak_device_vram_mib=max(x['gpu_device_memory_mib'] for x in window),peak_server_rss_mib=max(x['server_working_set_bytes'] for x in window)/2**20)
   jpath=ROOT/'judgments'/split/aid/(c['id']+'.json');j=read(jpath) if jpath.exists() else {}
   row['semantic_evaluated']=j.get('status')=='evaluated'
   if row['semantic_evaluated']:
    z=j['result'];items={x['id']:x for x in j['items']};facts=sum(x['facts_total'] for x in z['items']);supported=sum(x['facts_supported'] for x in z['items']);cites=sum(len(x['doc_ids']) for x in items.values());citeok=sum(len(set(x['supported_citations'])) for x in z['items']);citedfacts=sum(x['facts_supported'] for x in z['items'] if x['supported_citations']);actions=[x for x in z['items'] if items[x['item_id']]['kind']=='actions']
    row.update(facts_total=facts,facts_supported=supported,citations_total=cites,citations_supported=citeok,facts_cited_supported=citedfacts,actions_total=len(actions),actions_unsupported=sum(not x['action_supported'] for x in actions),correctness=z['correctness'] if c['answerable'] else None,essential_total=z['essential_total'] if c['answerable'] else 0,essential_covered=z['essential_covered'] if c['answerable'] else 0,conditions_total=len(ann.get(c['id'],{}).get('conditions',[])),conditions_preserved=sum(z['conditions_preserved']),procedure_total=len(ann.get(c['id'],{}).get('actions',[])),procedure_covered=sum(z['procedure_units_covered']),useful_partial=int(z['useful_partial'] and r['status']=='partial'),critical_error=int(bool(z['critical_errors'])))
   out.append(row)
 return out

def aggregate(rs):
 def total(k):return sum(r.get(k,0) or 0 for r in rs)
 def mean(k):
  v=[r[k] for r in rs if r.get(k)is not None];return float(np.mean(v)) if v else None
 sem=[r for r in rs if r.get('semantic_evaluated')];ap=ratio(total('abstain_tp'),total('abstain_pred'));ar=ratio(total('abstain_tp'),total('ood'));lat=[r['seconds'] for r in rs]
 return {'n':len(rs),'n_answerable':total('good'),'n_ood':total('ood'),'document_groups':len({r['group'] for r in rs}),'semantic_evaluated':len(sem),'correctness_evaluated':sum(r.get('correctness')is not None for r in rs),'Answer Correctness [self-judge estimate]':mean('correctness'),'Faithfulness [self-judge estimate]':ratio(total('facts_supported'),total('facts_total')),'Unsupported Claim Rate [self-judge estimate]':ratio(total('facts_total')-total('facts_supported'),total('facts_total')),'Condition Preservation Rate [exploratory annotation + self-judge]':ratio(total('conditions_preserved'),total('conditions_total')),'Structured action unsupported rate [self-judge diagnostic; not full UAR]':ratio(total('actions_unsupported'),total('actions_total')),'Procedure Completeness [exploratory annotation + self-judge]':ratio(total('procedure_covered'),total('procedure_total')),'Citation Precision [semantic self-judge estimate]':ratio(total('citations_supported'),total('citations_total')),'Citation Recall [semantic self-judge estimate]':ratio(total('facts_cited_supported'),total('facts_total')),'Gold document ID Precision [exact]':ratio(total('id_correct'),total('id_pred')),'Gold document ID Recall [exact]':ratio(total('id_correct'),total('id_gold')),'False Refusal Rate [exact]':ratio(total('false_refusal'),total('good')),'False Answer Rate OOD [exact]':ratio(total('false_answer'),total('ood')),'Abstention Precision [exact]':ap,'Abstention Recall [exact]':ar,'Abstention F1 [exact]':2*ap*ar/(ap+ar) if ap is not None and ar is not None and ap+ar else None,'JSON Validity [schema, observed responses]':mean('json_valid'),'Contract Validity [exact]':mean('contract_valid'),'Error Rate [exact]':mean('error'),'Partial Answer Rate [exact]':mean('partial'),'Useful Partial / All Partial [self-judge estimate]':ratio(total('useful_partial'),sum(r['partial'] for r in sem)),'Essential reference coverage [self-judge estimate]':ratio(total('essential_covered'),total('essential_total')),'Critical-error answer rate [self-judge flags, unverified]':ratio(total('critical_error'),len(sem)),'Median Latency seconds':float(np.median(lat)) if lat else None,'p95 Latency seconds':float(np.percentile(lat,95)) if lat else None,'Peak VRAM MiB [device-wide sampled]':max((r.get('peak_device_vram_mib',0) for r in rs),default=0) or None,'Peak server working set MiB [sampled]':max((r.get('peak_server_rss_mib',0) for r in rs),default=0) or None,'Mean output characters':mean('output_chars'),'Median answered latency seconds':float(np.median([r['seconds'] for r in rs if r['status']in ['answered','partial']])) if any(r['status']in ['answered','partial'] for r in rs) else None,'Mean model calls':mean('calls'),'Mean prompt tokens':mean('prompt_tokens'),'Mean output tokens':mean('output_tokens'),'Mean Russian script share [nonempty outputs]':mean('russian_script_share'),'facts_denominator_estimated':total('facts_total'),'actions_denominator_estimated':total('actions_total'),'conditions_denominator_annotated':total('conditions_total'),'procedure_denominator_annotated':total('procedure_total')}

BOOT_METRICS=['Answer Correctness [self-judge estimate]','Faithfulness [self-judge estimate]','Gold document ID Recall [exact]','False Refusal Rate [exact]','False Answer Rate OOD [exact]','Median Latency seconds']
def bootstrap(rs,ds):
 base={r['case_id']:r for r in rs if r['dataset']==ds and r['arm']=='A0'};out=[];rng=np.random.default_rng(20261113)
 for arm in ['A1','A2','A3','A4']:
  other={r['case_id']:r for r in rs if r['dataset']==ds and r['arm']==arm};ids=sorted(base.keys()&other.keys());groups=collections.defaultdict(list)
  for i in ids:groups[base[i]['group']].append(i)
  names=list(groups);aa=aggregate([base[i] for i in ids]);bb=aggregate([other[i] for i in ids]);samples={k:[] for k in BOOT_METRICS}
  for _ in range(2000):
   draw=[i for g in rng.choice(names,len(names),replace=True) for i in groups[g]];a=aggregate([base[i] for i in draw]);b=aggregate([other[i] for i in draw])
   for k in BOOT_METRICS:
    if a[k]is not None and b[k]is not None:samples[k].append(b[k]-a[k])
  for k in BOOT_METRICS:
   v=samples[k];out.append({'dataset':ds,'comparison':arm+' minus A0','metric':k,'paired_cases':len(ids),'groups':len(names),'resamples':2000,'difference':bb[k]-aa[k] if aa[k]is not None and bb[k]is not None else None,'ci95_low':float(np.percentile(v,2.5)) if v else None,'ci95_high':float(np.percentile(v,97.5)) if v else None,'valid_resamples':len(v),'warning':'Small group count; semantic metrics are same-model estimates, not independent annotations.'})
 return out

def write_csv(path,rs):
 keys=list(dict.fromkeys(k for r in rs for k in r))
 with path.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rs)

def main():
 rs=rows();write_csv(ROOT/'per_case_metrics.csv',rs)
 # Same evaluable questions in every arm; raw per-case judgments remain intact.
 common=set.intersection(*[{r['case_id'] for r in rs if r['arm']==a and r.get('semantic_evaluated')} for a in ARMS])
 semantic_fields=['facts_total','facts_supported','citations_total','citations_supported','facts_cited_supported','actions_total','actions_unsupported','correctness','essential_total','essential_covered','conditions_total','conditions_preserved','procedure_total','procedure_covered','useful_partial','critical_error']
 (ROOT/'semantic_coverage.json').write_text(json.dumps({'common_case_ids':sorted(common),'warning':'Same-model judge failed spot checks; diagnostic estimates only, not validated semantic measurements. Long-context skips and schema errors retained.','per_arm':{a:sum(r.get('semantic_evaluated',False) for r in rs if r['arm']==a) for a in ARMS}},ensure_ascii=False,indent=2),encoding='utf8')
 for r in rs:
  if r['case_id']not in common:
   r['semantic_evaluated']=False
   for k in semantic_fields:r.pop(k,None)
 summary=[]
 flags=read(ROOT/'procedure_annotations.json')['quality_flags']
 for ds in ['grounded_ru','multidoc2dial','multidoc2dial_clean_sensitivity']:
  for arm in ARMS:
   selected=[r for r in rs if r['arm']==arm and r['dataset']==('multidoc2dial' if ds.endswith('sensitivity') else ds) and (not ds.endswith('sensitivity') or r['case_id']not in flags)]
   summary.append(dict(dataset=ds,arm=arm,**aggregate(selected)))
 write_csv(ROOT/'metrics_comparison.csv',summary);(ROOT/'metrics_comparison.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
 boots=sum([bootstrap(rs,ds) for ds in ['grounded_ru','multidoc2dial']],[]);write_csv(ROOT/'paired_bootstrap.csv',boots)
 for a,aid in ARMS.items():
  result={'arm':a,'configuration_id':aid,'immutable_individual_results':'runs/<split>/'+aid,'test':[],'dev':[],'confirmation':[]}
  for split in ['dev','test','confirmation']:
   for c in read(ROOT/(split+'_cases.json')):
    p=ROOT/'runs'/split/aid/(c['id']+'.json')
    if p.exists():result[split].append({'input_and_gold':c,'result':read(p)})
  target=ROOT/('baseline_results.json' if a=='A0' else a.lower()+'_results.json')
  if not target.exists():
   with target.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
