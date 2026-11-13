$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
. (Join-Path $PSScriptRoot 'project-env.ps1')
if (Test-Path -LiteralPath 'data/processes.json') { throw 'Уже есть processes.json. Выполните stop.ps1 перед повторным запуском.' }
$pythonExe = Join-Path $PSScriptRoot '.venv313/Scripts/python.exe'
$llamaExe = Get-ChildItem -LiteralPath (Join-Path $PSScriptRoot 'tools/llama') -Recurse -Filter 'llama-server.exe' | Select-Object -First 1
if (-not $llamaExe) { throw 'Не найден llama-server.exe' }
New-Item -ItemType Directory -Path 'reports' -Force | Out-Null
$modelFile = Join-Path $PSScriptRoot 'models/llm3/qwen2.5-3b-instruct-q4_k_m.gguf'
$llmProcess = Start-Process -FilePath $llamaExe.FullName -ArgumentList '-m', ('"' + $modelFile + '"'), '--host','127.0.0.1','--port','8080','-c','8192','-t','4' -WindowStyle Hidden -PassThru -RedirectStandardOutput 'reports/llm.stdout.log' -RedirectStandardError 'reports/llm.stderr.log'
$appProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m','streamlit','run','app.py' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'reports/app.stdout.log' -RedirectStandardError 'reports/app.stderr.log'
@{ llm = $llmProcess.Id; app = $appProcess.Id; llmPath = $llamaExe.FullName; appPath = $pythonExe } | ConvertTo-Json | Set-Content -LiteralPath 'data/processes.json'
Write-Output 'Приложение запускается: http://127.0.0.1:8501. Логи в reports.'
