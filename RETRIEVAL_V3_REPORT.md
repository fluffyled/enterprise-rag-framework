# Retrieval V3 — итоговый отчёт

Дата: 2026-11-13. Ветка `sevsese` (v3-изменения в рабочем дереве, см. «Состояние репозитория»).
База: `RETRIEVAL_RESEARCH_REPORT.md`, стабильная архитектура V2
(BM25 + E5-small → RRF → mMiniLM → rule-based decomposition → coverage selection).

## Итог одной строкой

Польза Coverage-Aware Retrieval **подтверждена** на внешних данных с несколькими
требованиями на вопрос (LegalBench CUAD: Δ Evidence Recall@6 = +0.101,
95% CI [0.056–0.148]); алгоритмические усложнения (LLM-планировщик, улучшенные
правила, расширение пула, diversity-отбор) **не дали устойчивого прироста** и
отклонены; производительность улучшена в 1.5–14× без изменения качества
(CUDA + FastBM25 + batch CrossEncoder). End-to-end различий между baseline и
V2/V3 на test-сплите нет (0.90 у всех); потолок задан генерацией Qwen
(ORACLE-контекст даёт 0.85).

## Ключевые результаты

### Внешние benchmarks (CUDA, замороженные выборки; подробно — 02)

| Датасет | Метрика | B0 baseline | V2 coverage | BGE-M3 E2 |
|---|---|---:|---:|---:|
| MultiDoc2Dial 300 (en) | ER@6 | 0.6667 | 0.6667 | 0.6567 |
| LegalBench CUAD 200 (en) | ER@6 | 0.1588 | **0.2597** | 0.2127 |
| LegalBench CUAD 200 | AEH@6 | 0.120 | **0.210** | 0.165 |
| MIRACL pilot 50/2000 (ru) | Doc R@5 | 0.996 | 0.996 | 0.996 (pilot насыщен) |

### Внутренние сплиты (CUDA, 3079 фрагментов)

| Сплит | Конфиг | ER@6 | AEH@6 | MRR@10 | nDCG@10 | Медиана |
|---|---|---:|---:|---:|---:|---:|
| holdout (27q, диагностический) | B0 | 0.8125 | 0.7917 | 0.7431 | 0.7341 | 0.140 с |
| holdout | V2 | 0.8681 | 0.8333 | 0.8056 | 0.8063 | 0.167 с |
| holdout | V3-Final | 0.8681 | 0.8333 | 0.8056 | 0.8063 | **0.130 с** |
| test (20q, независимый) | B0 / V2 / V3-Final | 0.9250 | 0.9000 | 0.8946 | 0.9197 | 0.116 / 0.141 / 0.150 с |

### End-to-end (Qwen2.5-3B CUDA; подробно — 05)

- Success (прокси): B0 = V2 = V3F = 0.90; citation recall 0.925 у всех;
  abstention на неотвечаемых 3/3 верно у всех.
- **Oracle Context Experiment**: идеальный контекст → citation precision 1.0,
  но success 0.85 (два ложных отказа на изолированных gold spans).
  Генерация/калибровка abstain — текущий потолок, не retrieval.

### Производительность (подробно — 04)

- Перенос на CUDA: reranking 0.744 → 0.053 с (−14×); CPU p95 = 8.12 с → ≤ 0.98 с.
- FastBM25 (новый, `navigator/bm25_fast.py`): эквивалентность haystack доказана
  тестами и 300-запросным прогоном (0 отличий); этап BM25 0.198 → 0.0015 с;
  total MultiDoc2Dial median 0.403 → 0.193 с.
- batch CrossEncoder: идентичное качество, reranking mean −32%, p95 total −25%.
- Память: peak RSS ≈ 2.2–2.4 ГБ, VRAM ≈ 1.1–1.2 ГБ (retrieval), +3.1 ГБ VRAM при генерации Qwen.

## Принятые изменения (V3-Final)

`configs/retrieval_v3_final.yaml` = V2 coverage + `batch_cross_encoder: true`
+ FastBM25 (код) + `device: cuda`. Для продакшена обновить
`configs/retrieval_stable.yaml` на эти параметры (команда ниже не выполнялась
автоматически: stable.yaml — эталон сравнений).

## Отрицательные результаты (важно)

1. **D2 LLM-планировщик декомпозиции** — работает корректно (27/27 constrained JSON,
   без fallback), но повторяет качество правил при 9× latency (1.51 с vs 0.17 с). Отклонён.
2. **D1 улучшенные правила** — 20/20 на ручной разметке, но end-to-end потерял
   вопрос с условной клаузой (over-splitting). Отклонены существующие правила.
3. **Candidate pool 40** — лучший ER на holdout (+0.028), но значимая регрессия
   DocR@5 на MultiDoc2Dial (−0.037 [−0.070, −0.007]). Отклонён.
4. **Document diversity 0.05** — серьёзная регрессия ER@6 (0.87 → 0.69):
   принудительное разнообразие вытесняет доказательства одно-документных вопросов.
5. **BGE-M3 E2** — хуже coverage на CUAD и MultiDoc2Dial по ER@6 при latency ×2–3. Не используется.
6. **Token budget 1000–4000, min-subtask selection** — нулевой эффект на качестве;
   средний контекст ≈ 640 токенов, бюджет не ограничивает. Не внедрено.
7. **Exact-query embedding cache** — duplicate rate 0 на всех сплитах. Не внедрено.

## Ограничения данных и методов

- MIRACL — pilot (50/2000, incomplete judgments): различия методов не измеримы;
  полный корпус (сотни тысяч документов) — отдельная инженерная задача.
- MultiDoc2Dial: ~90% ошибок — span-level («документ найден, точный интервал
  не покрыт»); evidence_precision 0.024 отражает жёсткость пересечения, а не
  только качество. Улучшать надо чанкинг/span-отбор.
- Внутренние сплиты малы (60 вопросов суммарно); test n=20 → выводы опираются
  на согласованность четырёх корпусов, а не на мощную статистику одного сплита.
- End-to-end метрики — literal-overlap прокси без семантической ручной проверки;
  второй аннотатор не привлекался.
- E2E-оценка выполнена на одном LLM (Qwen2.5-3B q4_k_m); перенос выводов на
  другие модели не гарантирован.

## Дополнение: внешний датасет rag_eval_dataset_100 (2026-11-13)

100 размеченных вопросов сторонней разметки (ChatGPT) по внутренним документам
МФТИ, метрики их скриптом (Doc/Unit Hit@K, MRR). Подробно —
`reports/retrieval_v3/07_rag100_dataset.md`.

- **BGE-M3 E2 — лучший на этом корпусе** (test, n=74): Doc H@5 1.000 и Unit MRR 0.861
  против 0.987/0.805–0.812 у E5-конфигов; needle Recall 86/92 против 84/92;
  Δ Unit MRR +0.053 ± 0.047 против baseline (знак согласован, CI касается нуля).
- E5-конфиги на этом наборе почти не различаются; coverage-селектор снижает
  ранговые метрики selected-контекста (вопросы одно-требовательные).
- Это **не отменяет** вывод этапа 02: на LegalBench CUAD BGE хуже coverage
  (ER@6 0.213 против 0.260), на MultiDoc2Dial хуже baseline. Выбор варианта
  зависит от профиля вопросов: перефразные одно-документные вопросы → BGE-M3;
  многотребовательные юридические → coverage; нужна скорость → V3-Final (E5).

## Направления дальнейшей работы

1. **Генерация, не retrieval** (главное): калибровка abstain Qwen
   (ORACLE-ceiling 0.85), обучение/промптинг на полноте цитат, оценка больших LLM.
2. **Span-гранулярность**: чанкинг, привязанный к структуре документа
   (разделы/пункты), и span-level отбор после reranking.
3. **Полный MIRACL**: потоковая индексация полного корпуса, дисковый индекс
   (FAISS/Qdrant), официальные qrels.
4. **MultiDoc2Dial**: диалоговый контекст длиннее 1 реплики, больше запросов.
5. **Второй аннотатор** для внутренних сплитов и E2E-разметки.

## Воспроизводимость

- Окружение: conda `neuro_clean`, torch 2.11.0+cu126, RTX 3070 Ti 8 ГБ, 32 ГБ RAM.
- Индексы: `data/index.json` (internal, cuda, fp `a0b27b50…`),
  `data/experiment_indexes/<dataset>/<fingerprint>/`; CPU-версия `data/index.cpu.json`.
- Frozen-сплиты: `data/frozen_external_eval.json` (sha в метаданных каждого прогона).
- Отчёты этапов: `reports/retrieval_v3/01…06`; эксперименты:
  `reports/retrieval_experiments/v3_{holdout,test,cuda_*}_*`; сравнения:
  `reports/retrieval_experiments/v3_external_cuda/`.
- Тесты: `python -m pytest tests/` — 49 passed (включая эквивалентность FastBM25
  и batched CE).
- Командные очереди прогонов сохранены в выводе фоновых задач сессии;
  типовая команда: `python scripts/evaluate_retrieval.py --dataset <name>
  --config <cfg> [--limit N] --name <exp>`.

## Состояние репозитория

Новое/изменённое в v3: `navigator/bm25_fast.py` (+тест), `navigator/retrieval.py`
(FastBM25 + device), `navigator/backends.py`, `navigator/config.py`,
`navigator/query_analysis.py` (D1/правила), `navigator/selection.py`,
`navigator/evaluation/*` (end_to_end, error_analysis, legalbench/miracl loaders),
`scripts/` (report_external_v3 параметризован, профилировщик, evaluate_end_to_end_v3
и др.), `configs/retrieval_cuda_*.yaml`, `configs/retrieval_v3_*.yaml`, отчёты.
Изменения **не закоммичены** (по состоянию на конец работ) — коммит и публикация
на усмотрение владельца; экспериментные `config.json` фиксируют git_sha (`28e1e5c`,
dirty) для всех прогонов.
