$ErrorActionPreference = 'Stop'
$stateFile = Join-Path $PSScriptRoot 'data/processes.json'
if (-not (Test-Path -LiteralPath $stateFile)) { Write-Output 'Нет сохранённых процессов'; exit }
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
foreach ($role in @('app', 'llm')) {
    $processId = $state.$role
    $savedPath = $state.($role + 'Path')
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    $started = $state.($role + 'Started')
    if ($process -and $process.Path -eq $savedPath -and
        (-not $started -or $process.StartTime.ToUniversalTime().Ticks -eq $started)) {
        Stop-Process -InputObject $process
        Wait-Process -InputObject $process -Timeout 10 -ErrorAction SilentlyContinue
    }
}
Remove-Item -LiteralPath $stateFile
