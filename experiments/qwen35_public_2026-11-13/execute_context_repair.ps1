. D:\хакатон\project-env.ps1
$env:PYTHONIOENCODING='utf-8'
Set-Location D:\хакатон\experiments\qwen35_public_2026-11-13
while (-not (Test-Path -LiteralPath .\ALL_RUNS_DONE)) { Start-Sleep -Seconds 2 }
D:\хакатон\.venv\Scripts\python.exe study_context_repair.py
