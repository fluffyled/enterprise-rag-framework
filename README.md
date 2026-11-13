# enterprise-rag-framework

## Вторая часть — короткие ответы, ссылки, темы и CUDA

Новая реализация: [ANSWERING.md](ANSWERING.md). Запуск `.\start-answer.ps1`, интерфейс http://127.0.0.1:8502. Статус и ограничения: [ANSWERING_RESULTS.md](ANSWERING_RESULTS.md). Независимый контракт — `answering/contracts.py`. Ниже сохранены инструкции прежнего baseline первой части.

Навигатор сотрудника по внутренним регламентам
Локальный baseline для документов МФТИ из датасета хакатона: вопросы на русском, hybrid retrieval, ответы выдержками с проверкой источников. Исследование выполнено до реализации: [research.md](research.md), архитектура: [architecture.md](architecture.md).

## Полный отчет и план развития

[PROJECT_REPORT.md](PROJECT_REPORT.md): выполненная работа, все сохраненные метрики, ограничения, варианты алгоритмов и инструкции замены компонентов. Обезличенная сводка: [metrics/baseline_summary.json](metrics/baseline_summary.json). Новые алгоритмы пока не внедрены.

## Оборудование
Проверенный компьютер: 16 ГБ RAM, RTX 3050 Laptop 4 ГБ VRAM. Retrieval и reranker работают на CPU. LLM — Qwen2.5-3B-Instruct Q4_K_M через CPU llama.cpp. GPU не требуется. Модель 3B распространяется по Qwen Research License; коммерческая пригодность не заявляется. Требуется Python 3.13, около 8–12 ГБ диска под окружение/модели/инструменты; точные задержки и ограничения см. TEST_RESULTS.md.

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
uv python install 3.13 --no-bin
uv venv --python 3.13 .venv313 --seed
.\.venv313\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv313\Scripts\python.exe scripts/download_data.py
.\.venv313\Scripts\python.exe scripts/download_models.py
```
models.lock.json хранит SHA ревизий весов; downloader использует существующие SHA. Не удаляйте lock для воспроизводимого запуска. requirements-lock.txt фиксирует фактическое Windows окружение; для Linux используйте requirements.txt (платформенные пакеты различаются).

Установите Tesseract с русским и английским языками: [официальные инструкции Windows](https://github.com/UB-Mannheim/tesseract/wiki). Можно указать TESSERACT_CMD полным путём к tesseract.exe; на подготовленной машине используется tools/tesseract/tesseract.exe. Папку с traineddata указывать через TESSDATA_PREFIX только при нестандартной установке. На этой машине Tesseract не принимает кириллицу в пути tessdata: создана файловая ссылка D:/hackathon-work на D:/хакатон; ingestion автоматически использует её для TESSDATA_PREFIX. На другом компьютере с кириллицей в пути создайте аналогичную ASCII junction либо укажите ASCII путь TESSDATA_PREFIX.

Скачайте CPU Windows архив [llama.cpp b12284](https://github.com/ggml-org/llama.cpp/releases/tag/b12284) и распакуйте в tools/llama. Скрипт start.ps1 ищет llama-server.exe рекурсивно. Не запускайте два LLM-сервера на одном порту.

## Подготовка документов
```powershell
.\.venv313\Scripts\python.exe -m navigator.cli ingest
.\.venv313\Scripts\python.exe -m navigator.cli index
```
Для добавления/удаления документов измените data/raw и повторите оба шага. Индекс перестраивается целиком; OCR страниц кэшируется по SHA256. Ошибка любого файла блокирует замену chunks.json. Не используйте предыдущий индекс после неудачной перестройки. Неподдерживаемые форматы сообщаются как ошибки.

PDF сохраняет номера страниц, DOCX — абзацы и строки таблиц в исходном порядке, XLSX — лист/строку/адреса непустых ячеек. Формулы сохраняются вместе с cached value; пересчёт Excel не выполняется. OCR может ошибаться в номерах, датах и таблицах.

## Использование
Примеры: «Кто инициирует поиск сотрудника на вакансию?», «В какой срок УРП размещает объявление о вакансии?», «Как согласовать смету по Физтех-школе?». Найденные выдержки доступны даже при отказе модели. Абзацы и страницы названы рядом с каждым источником, номер в ответе соответствует списку источников.

Ручной запуск (две консоли):
```powershell
.\tools\llama\llama-server.exe -m .\models\llm3\qwen2.5-3b-instruct-q4_k_m.gguf --host 127.0.0.1 --port 8080 -c 8192 -t 4
.\.venv313\Scripts\python.exe -m streamlit run app.py
```
```powershell
.\.venv313\Scripts\python.exe -m navigator.cli ask "Кто инициирует поиск сотрудника?"
.\.venv313\Scripts\python.exe -m pytest -q
.\.venv313\Scripts\python.exe scripts/evaluate.py
```

## Приватность и GitHub
Никаких ключей API не требуется. Документы, индексы и запросы обрабатываются локально. Подготовка скачивает пакеты из PyPI/PyTorch, веса Hugging Face, инструменты GitHub и документы Google Drive. Ответы используют только локальный HTTP сервер. Телеметрия Haystack/HF/Streamlit отключена. Нет обязательных переменных окружения; опционально TESSERACT_CMD, TESSDATA_PREFIX.

.gitignore исключает data, reports (содержат выдержки), models, tools, .venv313, .env. Не публикуйте оригиналы и производные данные без разрешения владельца, даже если Drive доступен по ссылке. Перед push выполните `git status` и `git diff --cached`. Репозиторий: https://github.com/fluffyled/enterprise-rag-framework (публичный; первоначально создан приватным). В GitHub отправляются код, документация и конфигурация. Git имя в настройках не подтверждает аутентификацию аккаунта.

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

Реальные контрольные вопросы и эталонные выдержки находятся в локальном data/eval_cases.json и исключены из Git. TEST_RESULTS.md содержит общую сводку без текстов внутренних документов; подробные сценарии сохраняются локально в reports.

## Эксперимент генератора Qwen3.5-4B — 13 ноября 2026

[Итоговый технический отчёт](experiments/qwen35_public_2026-11-13/final_experiment_report.md), [данные и воспроизведение](experiments/qwen35_public_2026-11-13/README.md), [реальные ошибки до/после](experiments/qwen35_public_2026-11-13/error_analysis.md). Сохранены A0–A4, 502 case/configuration записи, парные сравнения и ограничения оценки. Универсальное улучшение не доказано; исходный генератор и Retrieval автоматически не переключены. Веса и скачанные полные корпуса остаются локально на D:.
