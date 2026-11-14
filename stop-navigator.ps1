$ErrorActionPreference = 'Stop'

try {
    & (Join-Path $PSScriptRoot 'stop.ps1')
    Write-Host 'Навигатор остановлен.'
} catch {
    Write-Host "Ошибка остановки: $($_.Exception.Message)"
    Read-Host 'Нажмите Enter'
    exit 1
}
