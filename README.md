# enterprise-rag-framework

Навигатор сотрудника по внутренним регламентам
Локальный baseline для документов МФТИ из датасета хакатона: вопросы на русском, hybrid retrieval, ответы выдержками с проверкой источников. Исследование выполнено до реализации: [research.md](research.md), архитектура: [architecture.md](architecture.md).

## Полный отчет и план развития

[PROJECT_REPORT.md](PROJECT_REPORT.md): исходная реализация и базовые метрики. Обезличенная сводка: [metrics/baseline_summary.json](metrics/baseline_summary.json). Исследованные алгоритмы и принятая V2-конфигурация описаны в [RETRIEVAL_RESEARCH_REPORT.md](RETRIEVAL_RESEARCH_REPORT.md); последующие эксперименты — в разделе Retrieval v3 ниже.

## Оборудование
Проверенный компьютер: 16 ГБ RAM, RTX 3070 Ti Laptop 8 ГБ VRAM. Стабильные E5 retrieval, mMiniLM reranker и Qwen2.5-3B-Instruct Q4_K_M работают на CUDA; BM25, RRF, selection, parsing и OCR выполняются на CPU. Экспериментальные baseline YAML сохраняют CPU-режим для сравнения. Модель 3B распространяется по Qwen Research License; коммерческая пригодность не заявляется. Требуется Python 3.11 и PyTorch с CUDA; точные smoke-замеры сохраняются локально в `reports/retrieval_v3/cuda_smoke.json` и `cuda_qwen_smoke.json`.

## Быстрый запуск Windows
Откройте PowerShell в папке проекта. На подготовленном компьютере окружение, инструменты, модели и данные уже созданы.
```powershell
.\start.ps1
```
Интерфейс: http://127.0.0.1:8501. start.ps1 запускает два скрытых процесса только на localhost. Остановка:
```powershell
.\stop.ps1
```

## Установка с нуля
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/download_data.py
.\.venv\Scripts\python.exe scripts/download_models.py
```
models.lock.json хранит SHA ревизий весов; downloader использует существующие SHA. Не удаляйте lock для воспроизводимого запуска. requirements-lock.txt фиксирует фактическое Windows окружение; для Linux используйте requirements.txt (платформенные пакеты различаются).

Установите Tesseract с русским и английским языками: [официальные инструкции Windows](https://github.com/UB-Mannheim/tesseract/wiki). Можно указать TESSERACT_CMD полным путём к tesseract.exe; на подготовленной машине используется tools/tesseract/tesseract.exe. Папку с traineddata указывать через TESSDATA_PREFIX только при нестандартной установке. На этой машине Tesseract не принимает кириллицу в пути tessdata: создана файловая ссылка D:/hackathon-work на D:/хакатон; ingestion автоматически использует её для TESSDATA_PREFIX. На другом компьютере с кириллицей в пути создайте аналогичную ASCII junction либо укажите ASCII путь TESSDATA_PREFIX.

Для GPU скачайте `llama-b12284-bin-win-cuda-12.4-x64.zip` и `cudart-llama-bin-win-cuda-12.4-x64.zip` из [llama.cpp b12284](https://github.com/ggml-org/llama.cpp/releases/tag/b12284) и распакуйте оба в `tools/llama-cuda`. CPU-сборка сохраняется отдельно в `tools/llama`. `start.ps1` выбирает CUDA при наличии CUDA-сборки и передаёт `-ngl 999`; принудительный CPU режим: `$env:NAVIGATOR_LLM_DEVICE='cpu'`, принудительный CUDA: `$env:NAVIGATOR_LLM_DEVICE='cuda'`. Не запускайте два LLM-сервера на одном порту.

## Подготовка документов
```powershell
.\.venv\Scripts\python.exe -m navigator.cli ingest
.\.venv\Scripts\python.exe -m navigator.cli index
```
Для добавления/удаления документов измените data/raw и повторите оба шага. Индекс перестраивается целиком; OCR страниц кэшируется по SHA256. Ошибка любого файла блокирует замену chunks.json. Не используйте предыдущий индекс после неудачной перестройки. Неподдерживаемые форматы сообщаются как ошибки.

PDF сохраняет номера страниц, DOCX — абзацы и строки таблиц в исходном порядке, XLSX — лист/строку/адреса непустых ячеек. Формулы сохраняются вместе с cached value; пересчёт Excel не выполняется. OCR может ошибаться в номерах, датах и таблицах.

## Использование
Примеры: «Кто инициирует поиск сотрудника на вакансию?», «В какой срок УРП размещает объявление о вакансии?», «Как согласовать смету по Физтех-школе?». Найденные выдержки доступны даже при отказе модели. Абзацы и страницы названы рядом с каждым источником, номер в ответе соответствует списку источников.

Ручной запуск (две консоли):
```powershell
.\tools\llama\llama-server.exe -m .\models\llm3\qwen2.5-3b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 8080 -c 8192 -t 4
.\.venv\Scripts\python.exe -m streamlit run app.py
```
```powershell
.\.venv\Scripts\python.exe -m navigator.cli ask "Кто инициирует поиск сотрудника?"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/evaluate.py
```

## Приватность и GitHub
Никаких ключей API не требуется. Документы, индексы и запросы обрабатываются локально. Подготовка скачивает пакеты из PyPI/PyTorch, веса Hugging Face, инструменты GitHub и документы Google Drive. Ответы используют только локальный HTTP сервер. Телеметрия Haystack/HF/Streamlit отключена. Нет обязательных переменных окружения; опционально TESSERACT_CMD, TESSDATA_PREFIX.

.gitignore исключает data, reports (содержат выдержки), models, tools, .venv, .env. Не публикуйте оригиналы и производные данные без разрешения владельца, даже если Drive доступен по ссылке. Перед push выполните `git status` и `git diff --cached`. Репозиторий: https://github.com/fluffyled/enterprise-rag-framework (публичный; первоначально создан приватным). В GitHub отправляются код, документация и конфигурация. Git имя в настройках не подтверждает аутентификацию аккаунта.

## Docker
Docker на этом компьютере не обнаружен. Конфигурация подготовлена, но её сборка здесь не проверена.
```sh
docker compose build
docker compose run --rm app python -m navigator.cli ingest
docker compose run --rm app python -m navigator.cli index
docker compose up -d
# остановка
docker compose down
```
До запуска скачайте модели и data/raw на хосте; каталог data монтируется с правом записи для индекса/OCR. LLM в Compose использует образ, собираемый из тега b12284 llama.cpp; модель лежит на volume. Только UI порт публикуется на localhost. Для Linux OCR устанавливается в Dockerfile.

## Ограничения
Ответы extractive; свободного пересказа нет. Exact-match цитат не доказывает их релевантность или полноту ответа. Актуальность редакций требует ручной проверки. Даты из имён — подсказки. Автоматическое применение отмен и изменений не реализовано. Возможные противоречия определяет малая LLM и может пропускать. Табличный layout OCR не восстановлен полностью. Полноценный parent-child merging не реализован. Подробности фактических проверок — TEST_RESULTS.md.

## Происхождение
Переиспользуются библиотечные компоненты [Haystack](https://github.com/deepset-ai/haystack), Apache-2.0, а не скопированный исходный код приложения. Перечень лицензий компонентов и весов: THIRD_PARTY.md.

Реальные контрольные вопросы и эталонные выдержки находятся в локальных файлах `data/eval_cases.json` и `data/retrieval_eval_*.json` и исключены из Git. TEST_RESULTS.md содержит общую сводку без текстов внутренних документов; подробные сценарии сохраняются локально в reports.

## Retrieval research и конфигурация

Полный научно-технический отчёт: [RETRIEVAL_RESEARCH_REPORT.md](RETRIEVAL_RESEARCH_REPORT.md). Приложение и CLI по умолчанию используют `configs/retrieval_stable.yaml`. Другой YAML можно задать через `NAVIGATOR_CONFIG` или `python -m navigator.cli --config configs/retrieval_baseline.yaml ask "Вопрос"`.

Предусмотрены независимые флаги `hierarchical`, `contextual`, `coverage_aware`, `adaptive`, `graph_expansion`, а также `embedding_backend`, `reranker_backend` и `device` (`cpu`, `cuda`, `auto`). По умолчанию активны E5-small, mMiniLM и coverage-aware selection с правиловой декомпозицией на CUDA; экспериментальные hierarchy/contextual/adaptive/graph выключены. При смене chunking, контекстного представления, embedding-модели или вычислительного устройства индекс обязательно перестраивается. Исходный рабочий CPU snapshot на проверенной машине сохранён локально как `data/index.cpu.json`.

Retrieval benchmark не вызывает Qwen:
```powershell
python scripts/prepare_internal_eval.py
python scripts/evaluate_retrieval.py --dataset internal --split dev --name baseline_dev --config configs/retrieval_baseline.yaml --repeat 3
python scripts/evaluate_retrieval.py --dataset internal --split holdout --name stable_holdout --config configs/retrieval_stable.yaml
python scripts/compare_experiments.py baseline_dev stable_dev --output reports/retrieval_experiments/stable
```

Внешние pilots:
```powershell
python scripts/evaluate_retrieval.py --dataset multidoc2dial --split validation --limit 4 --document-limit 5 --name multidoc2dial_pilot
python scripts/evaluate_retrieval.py --dataset legalbench --split privacy_qa --limit 4 --name legalbench_pilot
python scripts/evaluate_retrieval.py --dataset miracl --split dev --limit 2 --corpus-limit 100 --name miracl_pilot
```
LegalBench скачивает официальный архив локально; при готовых данных можно передать `--legal-data-dir`. MIRACL pilot не является официальной оценкой полного корпуса. Внутренние вопросы, исходные тексты, индексы и reports не публикуются.

BGE-M3 — отдельный эксперимент, а не замена основной модели:
```powershell
python scripts/download_bge_m3.py
python scripts/evaluate_retrieval.py --dataset internal --split dev --name bge_e2_dev --config configs/retrieval_e2_bge_sparse.yaml --rebuild
```
Доступны E1 dense, E2 dense+sparse, E3 late interaction и E4 full. Late interaction ограничена top-N кандидатов и работает на CPU. Точные параметры, число ошибок, CI и ресурсы сохраняются в `reports/retrieval_experiments/`.

## Retrieval v3

Методика и результаты: [RETRIEVAL_V3_REPORT.md](RETRIEVAL_V3_REPORT.md). Этап 1 выполняет поэтапный разбор gold evidence и Oracle Analysis; gold не передаётся рабочему retrieval:
```powershell
python scripts/analyze_retrieval_errors.py --baseline baseline_holdout --stable stable_holdout --split holdout
python scripts/evaluate_decomposition.py
python scripts/profile_retrieval_v3.py baseline_holdout stable_holdout
```

Расширенные внешние наборы запускаются последовательно на одном индексе для E5-конфигураций. Примеры основных выборок:
```powershell
python scripts/evaluate_retrieval.py --dataset multidoc2dial --split validation --limit 300 --name v3_multidoc_baseline --config configs/retrieval_baseline.yaml --rebuild
python scripts/evaluate_retrieval.py --dataset legalbench --split cuad --limit 200 --name v3_legal_baseline --config configs/retrieval_baseline.yaml --rebuild
python scripts/evaluate_retrieval.py --dataset miracl --split dev --limit 50 --corpus-limit 2000 --shard-limit 2 --name v3_miracl_baseline --config configs/retrieval_baseline.yaml --rebuild
python scripts/report_external_v3.py
```
MIRACL с ограничением шардов является воспроизводимым pilot, а не официальной оценкой полного корпуса. Для повторного использования совместимого индекса передайте `--index-path`; при смене embedding/chunking нужен `--rebuild`.

Новые параметры `decomposition_method` (`existing`, `improved`, `planner`), `coverage_cost_normalization`, `coverage_document_diversity`, `coverage_min_subtask` и `batch_cross_encoder` управляются YAML. По умолчанию экспериментальные варианты выключены; planner использует только localhost и возвращается к improved rules при ошибке. Новый независимый split `test` не используется для подбора параметров.

End-to-end сравнение использует одну локальную Qwen, одинаковый prompt/schema и неизменную проверку дословных цитат:
```powershell
python scripts/evaluate_end_to_end_v3.py --split test --experiment B0=configs/retrieval_baseline.yaml --experiment V2=configs/retrieval_stable.yaml --experiment Oracle=oracle
```
Автоматические correctness/citation значения являются proxy по annotated evidence; смысловая поддержка цитат требует отдельной ручной разметки. Отчёты и приватные выдержки остаются в исключённом из Git `reports/`.
