# Enterprise RAG

Локальный навигатор по внутренним регламентам. Fast и Quality используют BGE-M3 и BGE-reranker-v2-m3. Приложение поддерживает Legacy и экспериментальный G2 на локальной Qwen3.5-4B, показывает цитаты и позволяет индексацию PDF, DOCX и XLSX через Streamlit.

## Запуск на Windows

Из активированного окружения Python 3.13 выполните:

```powershell
python -m pip install -r requirements-cuda.txt
python scripts/download_models.py --bge
python scripts/download_answer_model.py
.\start.ps1
```

Для запуска требуется [llama.cpp CUDA b12284](https://github.com/ggml-org/llama.cpp/releases/tag/b12284). После проверки готовности откройте [интерфейс](http://127.0.0.1:8501). В разделе «Документы» загрузите регламент и постройте базу, затем задайте вопрос в разделе «Ассистент».

```powershell
.\stop.ps1
python -m pytest -q
```

[Инструкция запуска и диагностики](RUNBOOK.md) · [Архитектура](architecture.md) · [Карта интеграции](INTEGRATION_REPORT.md) · [Результаты](EVALUATION_REPORT.md) · [Ограничения](KNOWN_LIMITATIONS.md)

## Приватность и GitHub
Никаких ключей API не требуется. Документы, индексы и запросы обрабатываются локально. Подготовка скачивает пакеты из PyPI/PyTorch, веса Hugging Face, инструменты GitHub и документы Google Drive. Ответы используют только локальный HTTP сервер. Телеметрия Haystack/HF/Streamlit отключена. Нет обязательных переменных окружения; опционально TESSERACT_CMD, TESSDATA_PREFIX.

.gitignore исключает data, reports (содержат выдержки), models, tools, .venv, .env. Не публикуйте оригиналы и производные данные без разрешения владельца, даже если Drive доступен по ссылке. Перед push выполните `git status` и `git diff --cached`. Репозиторий: https://github.com/fluffyled/enterprise-rag-framework (публичный; первоначально создан приватным). В GitHub отправляются код, документация и конфигурация. Git имя в настройках не подтверждает аутентификацию аккаунта.

## Ограничения

Актуальность редакций требует ручной проверки. Условия экспериментального режима G2 и ограничения OCR и исходных ссылок описаны в [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

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
