$ErrorActionPreference = 'Stop'
$stateFile = Join-Path $PSScriptRoot 'data/answer-processes.json'
if (-not (Test-Path -LiteralPath $stateFile)) { Write-Output 'Процессы второй части не сохранены'; exit }
$state = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
foreach ($role in @('app','llm')) {
    $processId = $state.$role
    $savedPath = $state.($role + 'Path')
    $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if ($process -and $process.Path -eq $savedPath) {
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$processId"
        foreach ($child in $children) {
            if ($role -eq 'app' -and $child.CommandLine -like '*streamlit*answer_app.py*') { Stop-Process -Id $child.ProcessId -ErrorAction SilentlyContinue }
        }
        Stop-Process -Id $processId -ErrorAction SilentlyContinue
    }
}
Remove-Item -LiteralPath $stateFile
