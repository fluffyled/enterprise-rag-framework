param([switch]$Cpu)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
. (Join-Path $PSScriptRoot 'project-env.ps1')
$pythonExe = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$modelLock = Get-Content -LiteralPath 'answer-model.lock.json' -Raw | ConvertFrom-Json
$modelFile = Join-Path $PSScriptRoot ($modelLock.local_dir + '/' + $modelLock.filename)
if ($Cpu) {
    $llamaExe = Join-Path $PSScriptRoot 'tools/llama/llama-server.exe'
    $gpuLayers = 0
} else {
    $runtimeLock = Get-Content -LiteralPath 'answer-runtime.lock.json' -Raw | ConvertFrom-Json
    $llamaExe = Join-Path $PSScriptRoot ($runtimeLock.directory + '/llama-server.exe')
    $gpuLayers = $runtimeLock.gpu_layers
}
if (-not (Test-Path -LiteralPath $llamaExe)) { throw 'Скачайте runtime по ANSWERING.md или используйте -Cpu' }
if (-not (Test-Path -LiteralPath $modelFile)) { throw 'Сначала скачайте модель по ANSWERING.md' }
if (Test-Path -LiteralPath 'data/answer-processes.json') { throw 'Сначала выполните stop-answer.ps1' }
New-Item -ItemType Directory -Path 'reports' -Force | Out-Null
$llmProcess = Start-Process -FilePath $llamaExe -ArgumentList '-m',('"'+$modelFile+'"'),'--host','127.0.0.1','--port','8081','-c','8192','-t','4','--parallel','1','--gpu-layers',([string]$gpuLayers) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'reports/answer-llm.stdout.log' -RedirectStandardError 'reports/answer-llm.stderr.log'
$appProcess = Start-Process -FilePath $pythonExe -ArgumentList '-m','streamlit','run','answer_app.py','--server.port','8502' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'reports/answer-ui.stdout.log' -RedirectStandardError 'reports/answer-ui.stderr.log'
@{llm=$llmProcess.Id;app=$appProcess.Id;llmPath=$llamaExe;appPath=$pythonExe} | ConvertTo-Json | Set-Content -LiteralPath 'data/answer-processes.json' -Encoding UTF8
Write-Output 'Вторая часть запускается: http://127.0.0.1:8502'
