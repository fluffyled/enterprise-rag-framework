import json,time,copy
from baseline import ROOT,a0,SESSION
import run_v2,variants,procedure_v3
from structured_context import source_sections_with_headings
p=ROOT;i='97b89d77600b3661ce5a2942127643cb-9';c=next(x for x in json.loads((p/'test_cases.json').read_text(encoding='utf8')) if x['id']==i);fixed=copy.deepcopy(c)
raw=json.loads((p/'data/multidoc2dial_doc.json').read_text(encoding='utf8'))['doc_data'];key=c['documents'][0]['id'];doc=next(d[key] for d in raw.values() if key in d);refs=[{'id_sp':x['span_id']} for x in c['gold_spans']]
fixed['documents'][0]['text']=source_sections_with_headings(doc,refs);assert fixed['documents'][0]['text'].startswith('Do not\n')
results={}
for arm,fn in [('A0',a0),('A1',variants.a1),('A2',lambda q:variants.staged(q,'A2')),('A3',procedure_v3.a3),('A4',lambda q:variants.staged(q,'A4'))]:
 packets=[]
 def hook(r,*a,**kw):packets.append({'request':json.loads(r.request.body),'response':r.json()})
 SESSION.hooks['response']=[hook];t=time.perf_counter()
 try:r=fn(fixed)
 except Exception as e:r={'status':'error','error':repr(e),'claims':[],'actions':[],'calls':packets}
 results[arm]=dict(seconds=time.perf_counter()-t,**r);print('heading repair',arm,r['status'],flush=True)
with (p/'context_repair_study.json').open('x',encoding='utf8') as f:json.dump({'note':'Unblinded diagnostic case study after identifying omitted source heading. Not part of original paired benchmark; original inputs/results unchanged. Gold reference itself is unreliable; no reference-based score reported.','original_case':c,'repaired_case':fixed,'results':results},f,ensure_ascii=False,indent=2)
(p/'REPAIR_DONE').write_text('done')
