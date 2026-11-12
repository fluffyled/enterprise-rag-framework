$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

try {
    & (Join-Path $PSScriptRoot 'start.ps1')
} catch {
    Write-Host "Ошибка запуска: $($_.Exception.Message)"
    Write-Host 'Если приложение уже запущено, сначала выполните "Остановить навигатор.cmd".'
    Read-Host 'Нажмите Enter'
    exit 1
}

Write-Host 'Модель загружается, подождите...'
$ok = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8080/health' -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $ok = $true; break }
    } catch {}
    Start-Sleep -Seconds 5
}
if ($ok) {
    Start-Sleep -Seconds 3
    Start-Process 'http://127.0.0.1:8501'
    Write-Host 'Навигатор открыт в браузере: http://127.0.0.1:8501'
    Start-Sleep -Seconds 5
} else {
    Write-Host 'Модель не ответила за 3 минуты. Откройте http://127.0.0.1:8501 вручную через минуту.'
    Read-Host 'Нажмите Enter'
}
