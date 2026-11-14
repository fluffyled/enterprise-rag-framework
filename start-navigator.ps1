param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

try {
    $python = $env:NAVIGATOR_PYTHON
    if (-not $python) {
        foreach ($candidate in '.venv/Scripts/python.exe', "$env:USERPROFILE/.conda/envs/neuro_clean/python.exe") {
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                $python = (Resolve-Path -LiteralPath $candidate).Path
                break
            }
        }
    }
    if (-not $python) { $python = 'python' }

    $preparedIndex = 'data/experiment_indexes/internal/f08c5dd40c32277b/index.json'
    if (-not $env:NAVIGATOR_INDEX -and (Test-Path -LiteralPath $preparedIndex -PathType Leaf)) {
        $env:NAVIGATOR_INDEX = $preparedIndex
    }

    Write-Host 'Запускаю модель и интерфейс…'
    $address = & (Join-Path $PSScriptRoot 'start.ps1') -Python $python
    Write-Host "Навигатор доступен по адресу $address"
    if (-not $NoBrowser) { Start-Process $address }
} catch {
    Write-Host "Ошибка запуска: $($_.Exception.Message)"
    if (-not $NoBrowser) { Read-Host 'Нажмите Enter' }
    exit 1
}
