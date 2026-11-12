. D:\хакатон\project-env.ps1
$env:PYTHONIOENCODING='utf-8'
Set-Location D:\хакатон\experiments\qwen35_public_2026-11-13
while ((Get-ChildItem -LiteralPath .\runs\dev\A4_v2 -Filter *.json).Count -lt 28) { Start-Sleep -Milliseconds 500 }
@"
import pathlib,json,hashlib,datetime,shutil
p=pathlib.Path.cwd();files=['baseline.py','variants.py','run_v2.py','prepare.py','dev_cases.json','test_cases.json','procedure_annotations.json','document_groups.json','evaluate_semantic.py']
lock={'locked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'purpose':'Generation prompts and selections frozen before first held-out model prediction. No tuning on test.','preferred_dev_candidate':'A2_v2 conservative evidence-first; A4 remains exploratory because of OOD partial answers. Test may invalidate recommendation, never tune its prompts.','arms':['A0_baseline','A1','A2_v2','A3_v2','A4_v2'],'hashes':{f:hashlib.sha256((p/f).read_bytes()).hexdigest() for f in files},'note':'Some dev v0/v2 calls overlapped in single-slot server queue. Dev latency is not a controlled speed comparison; test is serial.'}
with (p/'pretest_lock.json').open('x',encoding='utf8') as f:json.dump(lock,f,ensure_ascii=False,indent=2)
for name in ['variants.py','run_v2.py']:shutil.copyfile(p/name,p/'frozen'/name)
print('HELD-OUT CONFIGURATION LOCKED',flush=True)
"@ | D:\хакатон\.venv\Scripts\python.exe -
foreach ($arm in @('A0_baseline','A1','A2_v2','A3_v2','A4_v2')) {
 D:\хакатон\.venv\Scripts\python.exe run_v2.py $arm test
 if ($LASTEXITCODE -ne 0) { throw "Failed $arm" }
}
D:\хакатон\.venv\Scripts\python.exe evaluate_semantic.py test
