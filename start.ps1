$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path -LiteralPath 'data/processes.json') { throw 'Уже есть processes.json. Выполните stop.ps1 перед повторным запуском.' }
$pythonExe = 'C:\Users\valera\.conda\envs\neuro_clean\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) { throw "Не найден python окружения neuro_clean: $pythonExe" }
$cudaExe = Join-Path $PSScriptRoot 'tools/llama-cuda/llama-server.exe'
$llmDevice = if ($env:NAVIGATOR_LLM_DEVICE) { $env:NAVIGATOR_LLM_DEVICE } elseif (Test-Path -LiteralPath $cudaExe) { 'cuda' } else { 'cpu' }
if ($llmDevice -eq 'cuda') {
    if (-not (Test-Path -LiteralPath $cudaExe)) { throw 'NAVIGATOR_LLM_DEVICE=cuda, но tools/llama-cuda/llama-server.exe не найден' }
    $llamaPath = $cudaExe
} elseif ($llmDevice -eq 'cpu') {
    $llamaExe = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'tools/llama') -Recurse -Filter 'llama-server.exe' | Select-Object -First 1
    if (-not $llamaExe) { throw 'Не найден llama-server.exe' }
    $llamaPath = $llamaExe.FullName
} else { throw 'NAVIGATOR_LLM_DEVICE должен быть cpu или cuda' }
New-Item -ItemType Directory -Path 'reports' -Force | Out-Null
$modelFile = Join-Path $PSScriptRoot 'models/llm3/qwen2.5-3b-instruct-q4_k_m.gguf'
$llmArgs = @('-m', ('"' + $modelFile + '"'), '--host','127.0.0.1','--port','8080','-c','8192','-t','4')
if ($llmDevice -eq 'cuda') { $llmArgs += @('-ngl', '999') }
$llmProcess = Start-Process -FilePath $llamaPath -ArgumentList $llmArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput 'reports/llm.stdout.log' -RedirectStandardError 'reports/llm.stderr.log'
$appProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m','streamlit','run','app.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'reports/app.stdout.log' -RedirectStandardError 'reports/app.stderr.log'
@{ llm = $llmProcess.Id; app = $appProcess.Id; llmPath = $llamaExe.FullName; appPath = $pythonExe } | ConvertTo-Json | Set-Content -LiteralPath 'data/processes.json'
Write-Output 'Приложение запускается: http://127.0.0.1:8501. Логи в reports.'
