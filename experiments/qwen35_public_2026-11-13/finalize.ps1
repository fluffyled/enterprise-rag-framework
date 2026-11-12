. D:\хакатон\project-env.ps1
$env:PYTHONIOENCODING='utf-8'
$env:MPLCONFIGDIR='D:\хакатон\.cache\matplotlib'
Set-Location D:\хакатон\experiments\qwen35_public_2026-11-13
while (-not (Test-Path -LiteralPath .\REPAIR_DONE)) { Start-Sleep -Seconds 2 }
Set-Content -LiteralPath .\STOP_MONITOR -Value done
Start-Sleep -Seconds 1
D:\хакатон\.venv\Scripts\python.exe -m pip freeze | Set-Content -LiteralPath .\requirements-lock.txt -Encoding UTF8
D:\хакатон\.venv\Scripts\python.exe metrics.py > .\metrics_build.log
if ($LASTEXITCODE -ne 0) { throw 'Metrics build failed' }
D:\хакатон\.venv\Scripts\python.exe build_report.py
if ($LASTEXITCODE -ne 0) { throw 'Report build failed' }
D:\хакатон\.venv\Scripts\python.exe build_final.py
if ($LASTEXITCODE -ne 0) { throw 'Final report build failed' }
D:\хакатон\.venv\Scripts\python.exe verify_artifacts.py
