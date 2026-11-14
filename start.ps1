param(
    [string]$Python = 'python',
    [string]$Server = '',
    [ValidateRange(0, 99)][int]$GpuLayers = 24
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path -LiteralPath 'data/processes.json') { throw 'Выполните stop.ps1 перед повторным запуском.' }
$pythonExe = (Get-Command -Name $Python -CommandType Application).Source
if (-not $Server) { $Server = 'tools/llama-cuda/llama-server.exe' }
$serverExe = (Resolve-Path -LiteralPath $Server).Path
$lock = Get-Content -Raw -LiteralPath 'answer-model.lock.json' | ConvertFrom-Json
$model = (Resolve-Path -LiteralPath (Join-Path $lock.local_dir $lock.filename)).Path
$env:LLM_ENDPOINT = 'http://127.0.0.1:8080/v1/chat/completions'
$env:ANSWER_LLM_ENDPOINT = $env:LLM_ENDPOINT
$env:NAVIGATOR_UI_MODE = 'Подключённый'
& $pythonExe -c 'from navigator.rag_service import application_config; application_config()'
if ($LASTEXITCODE -ne 0) { throw 'Ошибка окружения или application.yaml.' }
New-Item -ItemType Directory -Path 'data','reports' -Force | Out-Null
$llm = $null
$app = $null
try {
    $llmArgs = @('-m', ('"' + $model + '"'), '--host','127.0.0.1','--port','8080',
                 '-c','8192','--parallel','1','--cache-ram','512','-ngl',"$GpuLayers",'--reasoning','off')
    $llm = Start-Process -FilePath $serverExe -ArgumentList $llmArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput 'reports/llm.stdout.log' -RedirectStandardError 'reports/llm.stderr.log'
    $deadline = [DateTime]::UtcNow.AddMinutes(2)
    $ready = $false
    $probe = @{messages=@(@{role='user';content='Reply OK'});max_tokens=8;temperature=0} | ConvertTo-Json -Depth 5 -Compress
    while ([DateTime]::UtcNow -lt $deadline -and -not $llm.HasExited) {
        try {
            $reply = Invoke-RestMethod -Method Post -Uri $env:LLM_ENDPOINT -ContentType 'application/json' -Body $probe -TimeoutSec 5
            if ($reply.choices[0].message.content) { $ready = $true; break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready -or $llm.HasExited) { throw 'llama-server не прошёл пробную генерацию. См. reports/llm.stderr.log.' }
    $app = Start-Process -FilePath $pythonExe -ArgumentList '-m','streamlit','run','app.py','--server.address','127.0.0.1','--server.port','8501' -WindowStyle Hidden -PassThru -RedirectStandardOutput 'reports/app.stdout.log' -RedirectStandardError 'reports/app.stderr.log'
    $deadline = [DateTime]::UtcNow.AddSeconds(45)
    $ready = $false
    while ([DateTime]::UtcNow -lt $deadline -and -not $app.HasExited) {
        try {
            $ready = (Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8501/_stcore/health' -TimeoutSec 3).StatusCode -eq 200
            if ($ready) { break }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready -or $app.HasExited) { throw 'Streamlit недоступен. См. reports/app.stderr.log.' }
    @{llm=$llm.Id; app=$app.Id; llmPath=$serverExe; appPath=$pythonExe;
      llmStarted=$llm.StartTime.ToUniversalTime().Ticks; appStarted=$app.StartTime.ToUniversalTime().Ticks} |
        ConvertTo-Json | Set-Content -LiteralPath 'data/processes.json'
    Write-Output 'http://127.0.0.1:8501'
} catch {
    foreach ($process in @($app, $llm)) {
        if ($process -and -not $process.HasExited) { Stop-Process -InputObject $process }
    }
    throw
}
