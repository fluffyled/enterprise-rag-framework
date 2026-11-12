"""Small, fixed dev-only controls; never used to retune held-out prompts."""
import json,random,time,hashlib,copy
import run_v2
from baseline import ROOT,call
import variants as v

def one_step(c):
 opts=v.blocks(c);ids=[x['id'] for x in opts];lookup={x['id']:x for x in opts}
 item={'type':'object','properties':{'text':{'type':'string'},'evidence_ids':{'type':'array','items':{'type':'integer','enum':ids},'minItems':1}},'required':['text','evidence_ids'],'additionalProperties':False}
 schema={'type':'object','properties':{'status':{'type':'string','enum':['answered','insufficient','conflict']},'claims':{'type':'array','items':item,'maxItems':4}},'required':['status','claims'],'additionalProperties':False}
 r=call([{'role':'system','content':v.GENERATE},{'role':'user','content':v.present(c,opts)}],schema,600);x=r['parsed'];claims=[]
 for a in x['claims']:
  assert all(i in lookup for i in a['evidence_ids'])
  claims.append(dict(text=a['text'],evidence_ids=a['evidence_ids'],doc_ids=list(dict.fromkeys(lookup[i]['doc_id'] for i in a['evidence_ids']))))
 if x['status']=='insufficient':claims=[]
 return dict(status=x['status'],claims=claims,actions=[],calls=[r],options=opts)

def main():
 cases=json.loads((ROOT/'dev_cases.json').read_text(encoding='utf8'));good=[c for c in cases if c['dataset']=='grounded_ru' and c['answerable']][:3];bad=[c for c in cases if c['dataset']=='grounded_ru' and not c['answerable']][:3]
 jobs=[]
 for c in good:
  rel=[d for d in c['documents'] if d['id'] in c['gold_doc_ids']];other=[d for d in c['documents'] if d['id'] not in c['gold_doc_ids']]
  for label,docs in [('relevant_first',rel+other),('relevant_middle',other[:len(other)//2]+rel+other[len(other)//2:]),('relevant_last',other+rel),('short_oracle_gold_docs',rel)]:
   cc=copy.deepcopy(c);cc['documents']=docs;jobs.append((label,cc,False))
 for c in good+bad:jobs.append(('one_step_full',c,True))
 random.Random(20261113).shuffle(jobs);dest=ROOT/'ablations';dest.mkdir(exist_ok=True)
 for label,c,single in jobs:
  path=dest/(label+'_'+c['id']+'.json')
  if path.exists():continue
  t=time.perf_counter()
  try:r=one_step(c) if single else v.staged(c,'A2')
  except Exception as e:r={'status':'error','error':repr(e),'calls':[],'claims':[],'actions':[]}
  with path.open('x',encoding='utf8') as f:json.dump({'condition':label,'case':c,'seconds':time.perf_counter()-t,'result':r,'code_sha256':hashlib.sha256(open(__file__,'rb').read()).hexdigest()},f,ensure_ascii=False,indent=2)
  print('ablation',label,c['id'],r['status'],flush=True)
if __name__=='__main__':main()
