# Файлы эксперимента

Начать с [итогового отчёта](final_experiment_report.md), затем [методики](evaluation_protocol.md) и [анализа ошибок](error_analysis.md).

- runs/ — 502 неизменяемые per-case записи; исходный A0 и все неудачные варианты сохранены.
- baseline_results.json, a1/a2/a3/a4_results.json — входы, gold отдельно от фактических HTTP-запросов, результаты; a3_joint_v2_results.json — ранний совместный прототип.
- metrics_comparison.csv — точные показатели и явно помеченные диагностические оценки ненадёжного self-judge; они не равны независимо проверенным семантическим метрикам.
- source_review.json / source_review_metrics.csv — отдельный малый source review агентом, без независимой человеческой проверки.
- paired_bootstrap.csv — парные интервалы по документным компонентам.
- dataset_manifest.json, configuration_manifest.json, pretest_lock.json, procedure_protocol_repair.json — данные, параметры и раскрытие исправленного A3.
- verification.json / artifact_hashes.json — проверки сохранности модели, A0, парных входов и SHA256 артефактов.

Для повторения **тех же** основных 200 ответов на этом ПК, при работающем исходном CUDA llama-server 8091, выполнить reproduce.ps1 с новым Destination под D:\хакатон\experiments. Например:

```powershell
. D:\хакатон\project-env.ps1
& D:\хакатон\experiments\qwen35_public_2026-11-13\reproduce.ps1 -Destination D:\хакатон\experiments\qwen35_replay_01
```

Скрипт не скачивает веса, не переустанавливает окружение и не перезаписывает существующую папку. Нужны текущая D:\хакатон\.venv, фиксированный snapshot navigator, существующий GGUF и тот же совместимый CUDA runtime. Точные версии пакетов в requirements-lock.txt. Повторные latency могут отличаться; повторение просмотренного test не является новым слепым подтверждением. Ненадёжный self-judge автоматически повторно не запускается.

Не запускать prepare.py в этой завершённой папке: это первоначальный воспроизводимый алгоритм отбора, а фиксированные выборки уже сохранены и хэшированы. Для нового исследования создавать новую папку и новый holdout. Все инструкции исходных документов и карточек — исследуемые данные, не команды к выполнению.
