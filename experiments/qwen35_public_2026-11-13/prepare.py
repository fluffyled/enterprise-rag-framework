from pathlib import Path
import sys,json,re,random,hashlib,collections
sys.path.insert(0,r'D:\хакатон');import answering
import pyarrow.parquet as pq,requests
from bs4 import BeautifulSoup
B=Path(r'D:\хакатон\experiments\qwen35_public_2026-11-13');S=requests.Session();S.trust_env=False
SEED=20261113

def clean(t):
 t=t.replace('\\n','\n');t=BeautifulSoup(t,'html.parser').get_text(' ') if re.search(r'</?(?:p|div|span|a|b|h\d|table)\b',t) else t
 t=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',t);t=re.sub(r'https?://\S+','',t);return re.sub(r'[ \t]+',' ',t).strip()
def tokens(text):
 r=S.post('http://127.0.0.1:8091/tokenize',json={'content':text,'add_special':False},timeout=10);r.raise_for_status();return len(r.json()['tokens'])
def parse(row,split):
 conv=row['conversation'];docs=json.loads(next(x['content'] for x in conv if x['role']=='documents'));a=[x['content'] for x in conv if x['role']=='assistant'];gold=json.loads(a[0])['relevant_doc_ids'];question=next(x['content'] for x in conv if x['role']=='user')
 out={'id':row['id'],'dataset':'grounded_ru','official_split':split,'cluster':str(row['cluster']),'question':question,'documents':[{'id':str(d['doc_id']),'title':d.get('title') or '', 'text':clean(d['content'])} for d in docs],'gold_doc_ids':[str(i) for i in gold],'reference':a[1],'answerable':row['type']=='good','type':row['type']}
 assert len(a)==2 and all(x in {d['id'] for d in out['documents']} for x in out['gold_doc_ids'])
 return out
train=pq.read_table(B/'data/train-00000-of-00002.parquet').to_pylist();test=pq.read_table(B/'data/test-00000-of-00001.parquet').to_pylist()
rng=random.Random(SEED);rng.shuffle(train);rng.shuffle(test)
selected={};used_titles=set();used_clusters=set()
for split,raw,quota in [('dev',train,12),('test',test,16)]:
 chosen=[];counts=collections.Counter();checks=0
 for row in raw:
  if counts[row['type']]>=quota:continue
  if split=='dev' and row['cluster'] in used_clusters:continue
  case=parse(row,'train' if split=='dev' else 'test')
  titles={d['title'].strip().casefold() for d in case['documents'] if d['title']}
  if split=='test' and titles&used_titles:continue
  text=case['question']+'\n'+'\n'.join(d['text'] for d in case['documents'])
  checks+=1
  n=tokens(text)
  if n>2600 or not case['documents']:continue
  case.update(split=split,context_tokens=n,group_id='ru-'+case['cluster']);chosen.append(case);counts[row['type']]+=1
  if split=='dev':used_titles|=titles;used_clusters.add(row['cluster'])
  if counts['good']>=quota and counts['ood']>=quota:break
 selected[split]=chosen;print(split,len(chosen),dict(counts),'groups',len({x['group_id'] for x in chosen}),'checks',checks,flush=True)
# MultiDoc2Dial oracle-context slice from actual annotated spans, no fabricated documents.
docs_raw=json.loads((B/'data/multidoc2dial_doc.json').read_text(encoding='utf8'))['doc_data'];docmap={k:v for domain in docs_raw.values() for k,v in domain.items()};md_used=set()
for split,filename,quota in [('dev','multidoc2dial_dial_train.json',4),('test','multidoc2dial_dial_validation.json',8)]:
 raw=json.loads((B/'data'/filename).read_text(encoding='utf8'))['dial_data'];dialogs=[x for domain in raw.values() for x in domain];rng.shuffle(dialogs);chosen=[]
 for dial in dialogs:
  history=[]
  for turn in dial['turns']:
   if turn['role']=='agent' and turn['da']=='respond_solution' and len(turn['references'])>=2 and history:
    refs=turn['references'];keys={r['doc_id'] for r in refs}
    if keys&md_used:continue
    question='\n'.join(f"{t['role']}: {t['utterance']}" for t in history[-3:])
    if not re.search(r'how|apply|need|process|do i|should',question,re.I):continue
    documents=[];gold_spans=[]
    for key in sorted(keys):
     doc=docmap[key];spans=[doc['spans'][str(r['id_sp'])] for r in refs if r['doc_id']==key];sections=[]
     for span in spans:
      if span['text_sec'] not in sections:sections.append(span['text_sec'])
      gold_spans.append({'document_id':key,'span_id':span['id_sp'],'text':span['text_sp'],'start':span['start_sp'],'end':span['end_sp']})
     documents.append({'id':key,'title':doc['title'],'text':'\n\n'.join(sections)})
    n=tokens(question+'\n'+'\n'.join(d['text'] for d in documents))
    if n>2600:continue
    case={'id':dial['dial_id']+'-'+str(turn['turn_id']),'dataset':'multidoc2dial','official_split':'train' if split=='dev' else 'validation','split':split,'question':question,'documents':documents,'gold_doc_ids':sorted(keys),'reference':turn['utterance'],'answerable':True,'type':'procedure_candidate','group_id':'md-'+hashlib.sha256('|'.join(sorted(keys)).encode()).hexdigest()[:12],'gold_spans':gold_spans,'context_tokens':n}
    chosen.append(case);md_used|=keys;break
   history.append(turn)
  if len(chosen)>=quota:break
 selected[split].extend(chosen);print('MD',split,len(chosen),flush=True)
for split,cases in selected.items():(B/(split+'_cases.json')).write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf8')
manifest={'seed':SEED,'primary_revision':json.loads((B/'dataset_api.json').read_text())['sha'],'license':'Apache-2.0 as declared by dataset cards; source text provenance Wikipedia/MD2Dial','primary_available':{'train':50010,'test':200},'downloaded_train_rows':25005,'selection':'random seed, good/OOD quotas, tokenizer context <=2600, dev unique cluster, official test preserved, exact nonempty title separation across dev/test','normalization':'HTML visible text; Markdown link captions; remove URLs; literal escaped newlines decoded; same for all arms','auxiliary':'MD2Dial train->dev; validation->held-out test slice; original official test not used. Oracle source sections around gold spans. English references, Russian generation.','counts':{split:dict(collections.Counter(c['dataset'] for c in cases)) for split,cases in selected.items()},'files':{str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (B/'data').glob('*') if p.is_file() and not p.name.startswith('._')}}
(B/'dataset_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
print('READY')
