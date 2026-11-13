# Этап 1 — аудит оценки и фиксация baseline (rag100)

Дата: 2026-11-13. Проверка корректности и сопоставимости существующей системы
оценки до реализации новых стратегий. Retrieval-логика на этом этапе не менялась.

## 1. Карта реализации вариантов

| Вариант | Конфиг | Candidate generation | Reranking | Selection |
|---|---|---|---|---|
| B0 baseline | `configs/retrieval_cuda_baseline.yaml` | BM25 (FastBM25, `navigator/bm25_fast.py`) + E5-small dense → RRF (`navigator/retrieval.py:_hybrid_search`) | mMiniLM (`navigator/backends.py`) | top-k по скору |
| V2 MMR | `configs/retrieval_cuda_mmr.yaml` | то же | то же | MMR λ=0.7 |
| V2 stable coverage | `configs/retrieval_cuda_stable.yaml` | + декомпозиция правилами (`navigator/query_analysis.py`) | то же | coverage greedy (`navigator/selection.py`) |
| V3-Final | `configs/retrieval_v3_final.yaml` | как V2 | batch CrossEncoder | как V2 |
| BGE-M3 E2 | `configs/retrieval_cuda_bge_e2.yaml` | BGE-M3 dense + sparse (вес 0.5) → weighted RRF (`_weighted_rank_fusion`) | mMiniLM | top-k по скору |

## 2. Где считаются Hit@K и MRR

- **rag100**: сторонний `data/rag100/evaluate_retrieval.py` — по списку `retrieved`
  в predictions. Считалось два варианта: по reranked top-10 (**candidates**)
  и по итоговому контексту top-6 (**selected**, то, что получает LLM).
  По ответу LLM метрики retrieval не считаются; gold answer/needle в поиске не используются.
- **Внутренний benchmark** (`navigator/evaluation/benchmark.py:127`): основные метрики —
  по итоговому selected context; кандидаты (cross_encoder stage) используются только
  для error-анализа (наличие gold среди кандидатов).

Вывод: для сравнения «что видит LLM» корректный ряд — **selected**; candidates
характеризует потолок ранжирования. В отчётах 07/08 оба ряда приведены раздельно.

## 3. Соответствие индекса gold source-units

- Чанк→юнит: PDF — по `meta.page` (257 чанков); DOCX — текстовая привязка
  абзаца к чанку (632 привязаны, 26 сирот — таблицы/повторы, в gold не входят).
- **Все 55 уникальных gold source-units покрыты чанками индекса (55/55)**;
  все 92 needle посимвольно присутствуют в `corpus_units.jsonl` (проверено ранее).
- Ограничение: табличные чанки (`table_row`) в предсказания не мапятся;
  Q096 из-за этого имеет пустое предсказание у всех конфигураций одинаково.

## 4. Фактические сплиты метрик

| Метрика | Сплит | n |
|---|---|---|
| Doc/Unit Hit@K, MRR (таблица 07) | test | 74 отвечаемых (80 − 6 неотвечаемых) |
| Те же метрики, dev | dev | 18 отвечаемых |
| Needle Recall 86/92 | **оба сплита** (test+dev) | 92 отвечаемых |
| Abstention | не оценивался на retrieval-уровне (нет abstain-стадии) | — |

Расхождение «74 vs 92» объяснено: needle Recall считался по всем 92
отвечаемым, метрики датасета — по 74 тестовым. Далее needle Recall приводится
с указанием сплита.

## 5. Подбор параметров не выполнялся на test

- Все абляции V3 (coverage, бюджеты, декомпозиция, pool) — на внутреннем
  holdout и внешних CUAD/MultiDoc2Dial; финальная конфигурация выбрана там.
- rag100 до настоящего аудита использовался только для оценки; параметры под
  него не подбирались. Dev-часть rag100 (18q) зарезервирована для настройки
  новых стратегий (этапы 2–4).

## 6. Сопоставимость конфигураций

Одинаковые условия у всех 5 вариантов: одни 100 вопросов; `candidate_top_k=20`,
`output_top_k=6`, `context_token_budget=2000`, чанкинг 110/90 слов (для
mmr/bge_e2 заданы дефолтами `navigator/config.py`, проверено загрузкой
конфигов); один и тот же индекс чанков (E5-индекс `data/index.json`;
BGE — отдельный индекс с той же нарезкой `f08c5dd40c32277b`).
Различия только в перечисленных в п.1 механизмах. Одинаковый seed=42.

## 7. Фиксированные baseline

- Конфиги: `configs/retrieval_cuda_{baseline,mmr,stable,bge_e2}.yaml`,
  `configs/retrieval_v3_final.yaml` (содержимое — в git, sha в config.json прогонов).
- Версии моделей (`models.lock.json`): E5 `614241f6`, mMiniLM `1427fd65`,
  BGE-M3 `5617a9f6`, Qwen2.5-3B GGUF `7dabda4d`.
- Предсказания: `reports/retrieval_experiments/rag100/_<config>_{candidates,selected}_{test,dev}.jsonl`.
- Сводка с latency: `reports/retrieval_experiments/rag100/rag100_baseline_fixed.json`.
- **Воспроизводимость**: повторный прогон всех конфигураций дал побайтово
  идентичные метрики (проверено сравнением `rag100_summary_test.json` и
  `rag100_baseline_fixed.json`).
- Latency (медиана/p95, 100 вопросов, RTX 3070 Ti):
  B0 0.389/0.720 с; V2 0.429/0.779; MMR 0.410/0.770; V3F 0.417/0.850;
  BGE 0.776/1.236 с.

### Метрики fixed baseline (test, n=74, selected)

| Конфиг | Doc H@1 | Doc H@5 | Doc MRR | Unit H@1 | Unit H@5 | Unit MRR | Needle R (все 92) |
|---|---:|---:|---:|---:|---:|---:|---:|
| B0_baseline | 0.905 | 0.973 | 0.937 | 0.716 | 0.919 | 0.805 | 84/92 |
| V2_stable | 0.770 | 0.973 | 0.869 | 0.473 | 0.932 | 0.688 | 84/92 |
| V2_mmr | 0.905 | 0.987 | 0.938 | 0.716 | 0.932 | 0.802 | 84/92 |
| V3F_final | 0.770 | 0.973 | 0.869 | 0.473 | 0.932 | 0.688 | 84/92 |
| BGE_e2 | 0.946 | 1.000 | 0.970 | 0.797 | 0.932 | 0.858 | 86/92 |

## 8. Групповой bootstrap (2000 итераций, резampling по группам)

Вопросы, ссылающиеся на один gold source-unit / один документ, зависимы.
`scripts/grouped_bootstrap_rag100.py`; результаты:
`grouped_bootstrap.json`, `grouped_bootstrap_bge_vs_b0.json`.

| Сравнение (selected) | Метрика | Δ | 95% CI (по unit) | 95% CI (по doc) |
|---|---|---:|---|---|
| BGE − B0 | Unit MRR@10 | **+0.053** | [+0.008, +0.106] | [+0.008, +0.105] |
| BGE − B0 | Doc MRR@10 | +0.033 | [0.000, +0.075] | [0.000, +0.074] |
| BGE − V2 | Unit MRR@10 | **+0.170** | [+0.091, +0.238] | [+0.098, +0.226] |
| V2 − B0 | Unit MRR@10 | **−0.117** | [−0.176, −0.051] | [−0.182, −0.042] |
| V2 − B0 | Doc MRR@10 | −0.068 | [−0.113, −0.016] | [−0.132, 0.000] |
| MMR − B0 | все метрики | ≈0 | CI включают 0 | CI включают 0 |

Выводы: преимущество BGE-M3 E2 по Unit MRR статистически значимо даже при
групповой резampling-устойчивой проверке; падение ранговых метрик coverage —
тоже значимо (не шум). MMR нейтрален.

## 9. Таблица ошибок по вопросам

`reports/retrieval_v3/08_rag100_error_table.md` (74 вопроса × 5 конфигураций,
классификация retrieval_miss / unit_miss / ranking_error / selection_error).

Сводка (test, selected):

| Конфиг | ok | retrieval_miss | unit_miss | ranking_error | selection_error |
|---|---:|---:|---:|---:|---:|
| B0_baseline | 69 | 1 | 4 | 0 | 0 |
| V2_stable | 70 | 1 | 3 | 0 | 0 |
| V2_mmr | 69 | 1 | 4 | 0 | 0 |
| V3F_final | 70 | 1 | 3 | 0 | 0 |
| BGE_e2 | 70 | 0 | 3 | 0 | 1 |

Общие для всех ошибки: 1 retrieval_miss (Q096, табличный юнит без привязки)
и 3 unit_miss. Исправление табличной привязки — отдельная задача маппинга,
не retrieval.

## Итог этапа 1

Система оценки корректна и сопоставима; baseline воспроизводим побайтово;
BGE-M3 E2 значимо лучше E5-вариантов по Unit MRR на rag100 (групповой
bootstrap), coverage значимо снижает ранговые метрики selected-контекста на
однофактных вопросах. Новые стратегии настраивать только по dev-части rag100
и внешним корпусам, test — только финальная проверка.
