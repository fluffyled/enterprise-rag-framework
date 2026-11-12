"""A0 immutable baseline; all neural requests use the existing local CUDA server."""
from pathlib import Path
import sys,json,time,re,hashlib,requests,argparse
BASE=Path(r'D:\хакатон');ROOT=Path(__file__).parent
sys.path.insert(0,str(BASE));import answering
sys.path.insert(0,str(BASE/'.cache/llm-experiments/2026-11-12/sevsese'))
from navigator.answer import PROMPT,sentence_options,selected_quotes
from haystack import Document
SESSION=requests.Session();SESSION.trust_env=False

def call(messages,schema,max_tokens=300):
 payload={'messages':messages,'temperature':0,'seed':20261113,'max_tokens':max_tokens,'chat_template_kwargs':{'enable_thinking':False},'response_format':{'type':'json_object','schema':schema},'cache_prompt':False}
 start=time.perf_counter();r=SESSION.post('http://127.0.0.1:8091/v1/chat/completions',json=payload,timeout=180);r.raise_for_status();packet=r.json();choice=packet['choices'][0]
 record={'request':payload,'response':packet,'seconds':time.perf_counter()-start}
 if choice.get('finish_reason')!='stop':raise ValueError('truncated_generation')
 record['parsed']=json.loads(choice['message']['content']);return record

def schema0(options):
 ids={'type':'integer','enum':[o['id'] for o in options]}
 return {'type':'object','properties':{'answer_ids':{'type':'array','items':ids,'maxItems':3},'step_ids':{'type':'array','items':ids,'maxItems':5},'conflict_pairs':{'type':'array','items':{'type':'array','items':ids,'minItems':2,'maxItems':2},'maxItems':2},'insufficient':{'type':'boolean'}},'required':['answer_ids','step_ids','conflict_pairs','insufficient'],'additionalProperties':False}

def a0(case):
 docs=[Document(id=d['id'],content=d['text'],meta={'name':d['title']}) for d in case['documents']];opts=sentence_options(docs)
 if not opts:return {'calls':[],'status':'insufficient','claims':[],'actions':[],'options':opts}
 text='QUESTION: '+case['question']+'\nSOURCE SENTENCES:\n'+'\n'.join(f"[{o['id']}] {o['text']}" for o in opts)+'\nQUESTION: '+case['question']
 response=call([{'role':'system','content':PROMPT},{'role':'user','content':text}],schema0(opts));selection=response['parsed'];checked=selected_quotes(selection,opts,docs)
 claims=[{'text':x['quote'],'doc_ids':[docs[x['source']-1].id]} for x in checked['answer']];actions=[{'text':x['quote'],'doc_ids':[docs[x['source']-1].id]} for x in checked['steps']]
 return {'calls':[response],'status':'insufficient' if checked['status']=='insufficient' else 'answered','claims':claims,'actions':actions,'options':opts,'selection':selection}

def run(arm,split,fn):
 directory=ROOT/'runs'/split/arm;directory.mkdir(parents=True,exist_ok=True)
 for case in json.loads((ROOT/(split+'_cases.json')).read_text(encoding='utf8')):
  path=directory/(case['id']+'.json')
  if path.exists():continue
  t=time.perf_counter();record={'case_id':case['id'],'dataset':case['dataset'],'split':split,'arm':arm,'group_id':case['group_id'],'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'input_sha256':hashlib.sha256(json.dumps({k:case[k] for k in ['question','documents']},sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
  try:record.update(fn(case));record['valid']=True
  except Exception as e:record.update(status='error',valid=False,error=repr(e),claims=[],actions=[])
  record['seconds']=time.perf_counter()-t
  with path.open('x',encoding='utf8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
  print(split,arm,case['dataset'],case['id'],record['status'],round(record['seconds'],2),flush=True)
if __name__=='__main__':run('A0_baseline',sys.argv[1] if len(sys.argv)>1 else 'dev',a0)
