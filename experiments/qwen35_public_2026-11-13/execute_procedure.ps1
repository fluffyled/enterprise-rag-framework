. D:\хакатон\project-env.ps1
$env:PYTHONIOENCODING='utf-8'
Set-Location D:\хакатон\experiments\qwen35_public_2026-11-13
while (-not (Test-Path -LiteralPath .\diagnostics\A0_dev_error_replay.json)) { Start-Sleep -Seconds 2 }
D:\хакатон\.venv\Scripts\python.exe procedure_v3.py dev
D:\хакатон\.venv\Scripts\python.exe procedure_v3.py test
D:\хакатон\.venv\Scripts\python.exe run_v2.py A0_baseline confirmation
D:\хакатон\.venv\Scripts\python.exe procedure_v3.py confirmation
D:\хакатон\.venv\Scripts\python.exe evaluate_semantic.py test A3_procedure_v3
Set-Content -LiteralPath .\ALL_RUNS_DONE -Value done
