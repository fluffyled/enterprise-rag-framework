. D:\хакатон\project-env.ps1
$env:PYTHONIOENCODING='utf-8'
Set-Location D:\хакатон\experiments\qwen35_public_2026-11-13
while ((Get-ChildItem -LiteralPath .\judgments\test -Recurse -Filter *.json).Count -lt 200) { Start-Sleep -Seconds 2 }
D:\хакатон\.venv\Scripts\python.exe ablate.py
@"
import pathlib,json
import baseline as b
p=b.ROOT/'diagnostics';p.mkdir(exist_ok=True);c=next(x for x in json.loads((b.ROOT/'dev_cases.json').read_text(encoding='utf8')) if x['id']=='VrvPUoRruoKFsUREMkKtsu')
raw=[]
def hook(r,*a,**kw):raw.append({'request':json.loads(r.request.body),'response':r.json()})
b.SESSION.hooks['response']=[hook]
try:result=b.a0(c)
except Exception as e:result={'error':repr(e)}
with (p/'A0_dev_error_replay.json').open('x',encoding='utf8') as f:json.dump({'note':'Separate deterministic diagnostic replay, not the missing original HTTP packet. Original baseline result unchanged.','case':c,'calls':raw,'result':result},f,ensure_ascii=False,indent=2)
print('DIAGNOSTIC DONE')
"@ | D:\хакатон\.venv\Scripts\python.exe -
