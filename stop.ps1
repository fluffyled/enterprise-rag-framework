$ErrorActionPreference = 'Stop'
$stateFile = Join-Path $PSScriptRoot 'data/processes.json'
if (-not (Test-Path -LiteralPath $stateFile)) { Write-Output 'Нет сохранённых процессов'; exit }
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
foreach ($role in @('llm', 'app')) {
    $processId = $state.$role
    $savedPath = $state.($role + 'Path')
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process -and $process.Path -eq $savedPath) { Stop-Process -Id $processId }
}
Remove-Item -LiteralPath $stateFile
