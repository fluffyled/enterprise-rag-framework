param([Parameter(Mandatory=$true)][string]$Destination)
. D:\хакатон\project-env.ps1
$env:PYTHONIOENCODING='utf-8'
$targetPath=[IO.Path]::GetFullPath($Destination)
if (-not $targetPath.StartsWith('D:\хакатон\experiments\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Destination must be a new folder under D:\хакатон\experiments' }
if (Test-Path -LiteralPath $targetPath) { throw 'Destination already exists; choose a new directory to preserve results' }
$expectedHash='00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4'
if ((Get-FileHash -LiteralPath D:\хакатон\models\answer-llm\Qwen3.5-4B-Q4_K_M.gguf -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) { throw 'Model hash mismatch' }
New-Item -ItemType Directory -Path $targetPath | Out-Null
$files=@('baseline.py','variants.py','run_v2.py','procedure_v3.py','dev_cases.json','test_cases.json','model_manifest.json','configuration_manifest.json','pretest_lock.json','procedure_protocol_repair.json')
foreach ($name in $files) { Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $targetPath $name) }
Set-Location -LiteralPath $targetPath
@"
import requests
s=requests.Session();s.trust_env=False
p=s.get('http://127.0.0.1:8091/props',timeout=10).json()
assert p['default_generation_settings']['n_ctx']==4096
assert p['model_path'].endswith('Qwen3.5-4B-Q4_K_M.gguf')
assert p['build_info']
print('Replaying fixed inputs; this is not a fresh blind benchmark.')
"@ | D:\хакатон\.venv\Scripts\python.exe -
if ($LASTEXITCODE -ne 0) { throw 'Existing CUDA runtime check failed; no automatic installation or model download attempted' }
foreach ($arm in @('A0_baseline','A1','A2_v2','A4_v2')) {
 D:\хакатон\.venv\Scripts\python.exe run_v2.py $arm test
 if ($LASTEXITCODE -ne 0) { throw "Failed $arm" }
}
D:\хакатон\.venv\Scripts\python.exe procedure_v3.py test
