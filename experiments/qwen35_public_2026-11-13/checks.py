from pathlib import Path
import json,hashlib
R=Path(r'D:\хакатон\experiments\qwen35_public_2026-11-13');dev=json.loads((R/'dev_cases.json').read_text(encoding='utf8'));test=json.loads((R/'test_cases.json').read_text(encoding='utf8'))
def keys(cases):return {hashlib.sha256(d['text'].encode()).hexdigest() for c in cases for d in c['documents']}
assert not keys(dev)&keys(test),'Shared exact document text across splits'
print('NO EXACT DOCUMENT OVERLAP',len(dev),len(test))
# Meaningful representation checks, no new synthetic corpus.
import sys;sys.path.insert(0,str(R));from variants import blocks
for c in dev:
 for b in blocks(c):assert b['text'] in c['documents'][b['source']-1]['text']
print('A1 blocks are literal source substrings: PASS')
print('counts',[(ds,sum(c['dataset']==ds for c in dev),sum(c['dataset']==ds for c in test)) for ds in ['grounded_ru','multidoc2dial']])
