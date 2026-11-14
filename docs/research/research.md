# Исследование baseline
Дата: 11.11.2026. Основное приложение до этого документа не разрабатывалось; audit.py использовался только для исследования данных.

## Вывод
Основа — [Haystack](https://github.com/deepset-ai/haystack), готовые InMemoryBM25Retriever, InMemoryEmbeddingRetriever и DocumentJoiner с RRF. Малый корпус не требует отдельной БД. Локальные E5-small и multilingual MiniLM reranker на CPU оставляют VRAM для небольшой GGUF-модели. Обучение не требуется. Воспроизводимость библиотек проверяется установкой и pip freeze; ревизии моделей фиксируются SHA до загрузки.

## Научные работы
Численные результаты ниже относятся к публикациям, а не нашему корпусу. Где таблицы экспериментов не подтверждены, это явно указано.

| Работа | Проблема и архитектура | Модели, веса, код | Датасеты, метрики, подтверждённый результат | Применимость |
|---|---|---|---|---|
| [RAG, Lewis et al., 2020](https://arxiv.org/abs/2005.11401) | DPR + Wikipedia index + BART, RAG-Sequence/Token | [facebook/rag-sequence-nq](https://huggingface.co/facebook/rag-sequence-nq), [Transformers](https://github.com/huggingface/transformers) | NQ, TriviaQA, WebQuestions, CuratedTREC; EM; точные таблицы здесь не перепроверены | Базовый принцип retrieval перед генерацией; английские веса не выбираем |
| [Multilingual E5, 2024](https://arxiv.org/abs/2402.05672) | Контрастивный multilingual bi-encoder | [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small), MIT; [код](https://github.com/microsoft/unilm/tree/master/e5) | Mr.TyDi, MIRACL, MTEB; MRR/nDCG/Recall; точные значения не подтверждены | Русский язык, 384 измерения, 512 токенов; обязательны query:/passage: |
| [BGE-M3, 2024](https://arxiv.org/abs/2402.03216) | Dense+sparse+multi-vector, self-distillation | [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3), [FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding) | MIRACL, MKQA, MLDR; nDCG/Recall; >100 языков, до 8192 токенов; точные таблицы не подтверждены | Перспективен, но тяжелее E5-small при 16 ГБ RAM |
| [Passage Re-ranking with BERT, 2019](https://arxiv.org/abs/1901.04085) | Cross-encoder query+passage | BERT-large; [авторский код](https://github.com/nyu-dl/dl4marco-bert); исходные веса эксперимента отдельно не проверены | MS MARCO, MRR@10; численный результат не подтвержден | Применяем известный метод через [cross-encoder/mmarco-mMiniLMv2-L12-H384-v1](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1), Apache-2.0; это другая мультиязычная модель, обученная на mMARCO |
| [ALCE, 2023](https://arxiv.org/abs/2305.14627) | Проверяемые ответы с привязкой утверждений к источникам | Разные LLM и prompting; [код и данные](https://github.com/princeton-nlp/ALCE); единой модели нет | ASQA, QAMPARI, ELI5; correctness, citation precision/recall; даже лучшие модели на ELI5 не имеют полной поддержки цитатами примерно в 50% случаев | Проверять цитаты программно; наличие ссылки само по себе не доказывает ответ |
| [RAPTOR, 2024](https://arxiv.org/abs/2401.18059) | Иерархия кластеров и рекурсивных summaries | GPT-4 в опубликованном результате; [код](https://github.com/parthsarthi03/raptor); GPT-4 не имеет открытых весов | QuALITY; авторы сообщают +20 процентных пунктов accuracy относительно предыдущего лучшего результата при GPT-4 | Не выбираем генеративную иерархию: риск потери точных пунктов и стоимость; сохраняем структуру и соседние блоки |
| [Self-RAG, 2023](https://arxiv.org/abs/2310.11511) | Обучение retrieve/generate/reflect через специальные токены | [selfrag/selfrag_llama2_7b](https://huggingface.co/selfrag/selfrag_llama2_7b), [код](https://github.com/AkariAsai/self-rag); также 13B | Open-domain QA, fact verification, long-form; точные результаты и версии отдельных baseline не подтверждены | Полезен принцип проверки поддержки; полное воспроизведение избыточно |
| [SQuAD 2.0, 2018](https://arxiv.org/abs/1806.03822) | Невозможные вопросы, abstention | Extractive QA baselines, конкретные checkpoints не подтверждены; [данные](https://rajpurkar.github.io/SQuAD-explorer/) | >50 тыс. специально созданных unanswerable; в статье сильная система падает с 86 F1 на SQuAD1 до 66 F1 на SQuAD2 | Обязательны негативные и близкие к теме вопросы; retrieval score не вероятность |
| [DocVQA, 2020](https://arxiv.org/abs/2007.00398) | QA по изображению документа и OCR | OCR+reading baselines, версии весов здесь не подтверждены; [сайт](https://www.docvqa.org/) | 50 тыс. вопросов, 12 767 изображений; ANLS; численные результаты не подтверждены | Нужен контроль ошибок распознавания и табличной структуры |
| [WikiContradict, 2024](https://arxiv.org/abs/2406.13805) | Реальные противоречащие контексты Wikipedia | Несколько LLM; версии/веса и код не подтверждены в просмотренном abstract | 253 размеченных примера; авторы описывают проблемы отражения противоречий, особенно неявных | Не разрешать конфликт автоматически по более новой дате; показывать обе выдержки |

## Пять существующих проектов
Изучены официальные README, API документация и лицензии GitHub. Полное воспроизведение каждого проекта не выполнялось. У проектов нет единственной обязательной версии модели: приведенные ниже модели выбираются конфигурацией. Потребление RAM — оценка, не наш замер.

| Проект | Подготовка и поиск | Генерация, reranking, цитирование | Локальный запуск и ресурсы | Лицензия, адаптация |
|---|---|---|---|---|
| [Haystack](https://github.com/deepset-ai/haystack) | Компоненты конвертации, splitters, BM25+dense, RRF | Любой подключаемый local generator; rankers; document meta сохраняются, проверку цитат реализуем в адаптере | Python; in-memory store без сервера; модели определяют RAM | Apache-2.0; выбран. Минимум инфраструктуры, удобно тестировать отдельные этапы |
| [LlamaIndex](https://github.com/run-llama/llama_index) | Readers, hierarchical nodes, vector/BM25 через интеграции | Local LLM/embeddings, postprocessor rerank, citation query engine | Python, модели отдельно; несколько ГБ и выше | MIT; подходящая альтернатива, но больше интеграций для нашего минимального сценария |
| [RAGFlow](https://github.com/infiniflow/ragflow) | Deep document understanding, OCR/layout, hybrid retrieval | Model providers, reranking, traceable references | Docker и дополнительные сервисы; официально ориентирован на более ресурсоемкое развертывание | Apache-2.0; хорошо для сложных PDF, риск по 16 ГБ RAM и времени настройки |
| [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) | Document collector, workspace vector stores | Local providers, source citations; rerank зависит от версии/backend, универсальное наличие не подтверждено | Desktop или Docker; RAM зависит от выбранных моделей | MIT; легко показать UI, сложнее точно адаптировать пункты и редакции |
| [PrivateGPT](https://github.com/zylon-ai/private-gpt) | Ingestion/retrieval API, конфигурируемый storage | Local OpenAI-compatible inference, источники; rerank зависит от конфигурации | Python, local inference server; несколько сервисов | Apache-2.0; хорошая основа приватного API, лишняя инфраструктура для текущей демо |

Готовые компоненты поиска переиспользуются через библиотеку Haystack; исходники проектов не копируются. Точный pipeline: [официальный hybrid tutorial](https://haystack.deepset.ai/blog/hybrid-retrieval), [BM25](https://docs.haystack.deepset.ai/docs/inmemorybm25retriever), [DocumentJoiner](https://docs.haystack.deepset.ai/docs/documentjoiner). Запускаемым на этой машине решением считаем только наш проверенный адаптер, остальные — кандидаты, а не проверенные установки.

## Дополнительные датасеты
Они не скачиваются и не заменяют реальные документы.

| Датасет | Язык, размер | Лицензия | Назначение |
|---|---|---|---|
| [SQuAD2](https://rajpurkar.github.io/SQuAD-explorer/) | EN, около 150 тыс. train вопросов, включая негативные | CC BY-SA 4.0, см. сайт | Abstention, EM/F1; не проверяет российские регламенты |
| [HotpotQA](https://hotpotqa.github.io/) | EN, 113 тыс. QA | CC BY-SA 4.0, проверить состав артефактов перед распространением | Multi-hop, supporting facts, joint F1 |
| [SberQuAD](https://huggingface.co/datasets/kuznetsoffandrey/sberquad) | RU, train 45.3 тыс., три split; точный общий размер не перепроверен | В карточке unknown; не распространять без уточнения | Русский extractive QA, не редакции регламентов |
| [DocVQA](https://www.docvqa.org/) | EN, 50 тыс. вопросов / 12 767 изображений | Условия доступа сайта; разрешение на перераспространение не подтверждено | OCR и layout QA |
| [ALCE](https://github.com/princeton-nlp/ALCE) | EN; ASQA/QAMPARI/ELI5; точный размер наборов уточнять в репозитории | Код и входные корпуса имеют разные условия; общая лицензия данных не подтверждена | Citation precision/recall, groundedness |
| [FinanceBench](https://huggingface.co/datasets/PatronusAI/financebench) | EN, открытая часть 150 QA | CC BY-NC 4.0 | Финансовые документы, таблицы и multi-document reasoning |
| [WikiContradict](https://arxiv.org/abs/2406.13805) | EN, 253 примера | MIT, подтверждено в Appendix H статьи | Негативные проверки противоречий |

## Сравнение вариантов и выбор
Все модели только локально. Оценки оборудования приблизительны до измерений. Не приписываем баллы хакатона без официальной оценки.

| Вариант | Модели и источники | Поиск | Плюсы / минусы | Оборудование, сложность, критерии |
|---|---|---|---|---|
| Классический dense RAG | [E5-small](https://huggingface.co/intfloat/multilingual-e5-small) + [Qwen2.5-1.5B GGUF Q4_K_M](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF) | cosine | Дешевый, перефразы; может терять номера приказов | CPU, 8–16 ГБ; низкая; слабее поиск точных терминов |
| Hybrid RAG | Те же веса | Haystack BM25+cosine+RRF | Номера и перефразы; нет pairwise rerank | CPU, 16 ГБ; низкая; сильнее критерий поиска 20 |
| **Hybrid+rerank+структура (выбран)** | E5-small + [mMiniLMv2-L12](https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1) + [Qwen2.5-3B Q4_K_M](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF) | top20 BM25/dense, RRF, rerank, до 6 контекстов | Точные источники и локальность; маленькая LLM может плохо синтезировать | CPU и опционально 4 ГБ GPU, 16 ГБ RAM; средняя; баланс всех 6 критериев |
| Heavy hybrid | [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) + [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) + [Qwen2.5-7B](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct-GGUF) | Qdrant hybrid | Более мощные компоненты; качество здесь не измерено, не гарантировано | Желательно >8 ГБ VRAM, 24+ ГБ RAM; средняя; риск развертывания 20 |
| RAPTOR/tree summaries | E5 + GPT-4 в оригинальной статье; открытого идентичного GPT-4 нет | Иерархия summary nodes | Глобальный контекст; дополнительные неподтвержденные summaries и внешний API | Стоимость/оборудование зависят от замены; высокая; не подходит приватности |

Первоначально Qwen2.5-3B GGUF отложена из-за Qwen Research License и выбрана Apache-2.0 Qwen2.5-1.5B. После тестов этот выбор пересмотрен: окончательная модель 3B и причины приведены в последнем разделе. Ограничиваем контекст и используем CPU для retrieval. FAISS оправдан на большем корпусе; Chroma добавляет хранилище, Qdrant отдельный сервис — здесь in-memory с локальным JSON snapshot проще. Для 20 документов точный cosine достаточен.

## Особенности данных и правила актуальности
Аудит reports/dataset_audit.json: 20 файлов, 9 PDF, 8 DOCX, 3 XLSX, 28 469 871 байт. PDFium нужен потому, что pypdf на части PDF падает с Odd-length string. Пять документов содержат страницы без текстового слоя (точное число см. аудит); OCR локальный Tesseract rus+eng. XLSX сохраняет адреса строк/ячеек, merged ranges и формулы отдельно от cached values, не вычисляет формулы сам. Некоторые max_column сильно превышают фактические данные из-за форматирования — не индексировать пустые ячейки.

Имеются ссылки на отмену прежних приказов, изменение процедур и документы 2026 года. Это не подтверждает полную цепочку редакций. Контрольные суммы выявляют точные дубликаты; совпадение названия или более новая дата не означают юридическое замещение. Поле даты из имени — date_hint, не дата вступления в силу. При неизвестной актуальности ответ явно предупреждает об этом. Изменения применяются только при подтвержденной связи и полноте источников; baseline не разрешает такие связи автоматически.

## Достаточность исследования
Исследованы основные методы и реальные реализации, выбран один существующий pipeline. Таблицы точных метрик всех научных экспериментов, лицензии некоторых вспомогательных датасетов и производительность альтернатив не перепроверены; это ограничения исследования, а не выдуманные результаты. Практический выбор опирается на формат корпуса, оборудование и проверяемые компоненты. Следующий этап — реализация и замеры на реальных данных.

## Уточненные опубликованные результаты

На [карточке E5-small](https://huggingface.co/intfloat/multilingual-e5-small#benchmark-results-on-mr-tydi): Mr.TyDi Avg MRR@10 = 64.4, RU = 60.8; BM25 = 33.3 в среднем и 32.9 RU. E5-base = 65.9 в среднем, E5-large = 70.5. Это результаты авторов на Mr.TyDi, не преимущество на нашем датасете. Таким образом, small выбран по сочетанию русского retrieval и CPU стоимости, а не по предположению о лучшем качестве.

[README RAGFlow](https://github.com/infiniflow/ragflow#-docker-deployment-prerequisites) рекомендует стартовую конфигурацию 4 CPU, 16 GB RAM и 50 GB диска, Docker >=24 и Compose >=2.26.1; локальные модели требуют дополнительных ресурсов. Это усиливает выбор легкого Haystack baseline на нашей машине.

## Уточнение выбора после проверки запуска и ответов

Первоначальная Qwen2.5-1.5B Q4_K_M не прошла проверки: ложные отказы, обрезанный JSON и нерелевантный выбор цитат, включая ложный ответ на негативный вопрос. На основе измерений, а не размера/новизны, заменена на Qwen/Qwen2.5-3B-Instruct-GGUF, файл qwen2.5-3b-instruct-q4_k_m.gguf, SHA ревизии 7dabda4d13d513e3e842b20f0d435c732f172cbe. Retrieval не изменён. Точность этой замены определяется только финальным прогоном TEST_RESULTS.md.

Модель 3B имеет Qwen Research License вместо Apache-2.0. Перед дальнейшим использованием и распространением сверять полные [условия](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/blob/main/LICENSE). Коммерческая пригодность здесь не утверждается. В Git веса не включаются. Решение первоначально отложить 3B из-за лицензии пересмотрено для локального baseline хакатона после фактических отказов 1.5B.

Формат ответа исправлен на constrained JSON с maxItems и enum допустимых номеров предложений, поддерживаемый [llama.cpp b12284](https://github.com/ggml-org/llama.cpp/blob/b12284/tools/server/README.md). Модель не копирует длинные цитаты; код извлекает выбранное предложение из источника и проверяет его. Это инженерное исправление воспроизводимого baseline, без обучения, нового retriever или экспериментальной архитектуры.
