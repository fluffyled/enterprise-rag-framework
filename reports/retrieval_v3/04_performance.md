# Retrieval v3 — производительность

Платформа: AMD Ryzen (16 логических CPU), 32 ГБ RAM, RTX 3070 Ti Laptop 8 ГБ,
torch 2.11.0+cu126. Замеры warm retrieval; cold initialization в latency.json экспериментов.

## История: CPU → CUDA (internal holdout, 27 вопросов)

| Конфигурация | Устройство | Медиана, с | Mean, с | p95, с |
|---|---|---:|---:|---:|
| baseline | CPU | 0.857 | 0.978 | 1.631 |
| stable (coverage) | CPU | 0.872 | 2.363 | **8.121** |
| baseline | CUDA | 0.140 | 0.143 | 0.153 |
| stable (coverage) | CUDA | 0.167 | 0.219 | 0.852 |

Причина CPU-хвоста stable (корреляция Пирсона): total × число подзадач = 0.92,
total × число CE-пар = 0.86 — декомпозиция запускала дополнительные проходы
retrieval+reranking, каждый со своими Python-накладными расходами.

Этапы stable на CUDA (internal): embedding 0.017, BM25 0.044, dense 0.064,
reranking 0.053, selection ~0.000002, декомпозиция (rules) ~0.00005 с.

## Внешние корпуса на CUDA (медиана / p95, с)

| Корпус (фрагментов) | baseline | coverage | bge_e2 |
|---|---:|---:|---:|
| MultiDoc2Dial (4735) | 0.40 / 0.73 | 0.53 / 0.98 | 1.52 / 2.39 |
| LegalBench CUAD (1424) | 0.26 / 0.29 | 0.84 / 0.95 | 0.57 / 0.64 |
| MIRACL pilot (2000) | 0.27 / 0.30 | 0.22 / 0.25 | 0.32 / 0.36 |

## Оптимизация 1: FastBM25 (принята)

Профилирование MultiDoc2Dial на CUDA показало, что после переноса нейросетей
на GPU bottleneck сместился в **BM25 haystack**: 0.198 с медианы (49% от total 0.403 с).
Причина: haystack пересчитывает IDF по всему словарю (O(vocab)) и скорит
документы в чистом Python при каждом запросе.

Реализация: `navigator/bm25_fast.py` — статистика корпуса строится один раз
(posting lists + IDF по той же формуле haystack 3.5.x), запрос скорится
векторно через numpy. Эквивалентность доказана тестами
(`tests/test_bm25_fast.py`): top-k списки и скоры совпадают с haystack
на синтетическом корпусе включая тай-брейки (stable sort), пустые документы
и повторы токенов в запросе.

Проверка на полном benchmark (300 запросов MultiDoc2Dial, baseline CUDA):

| Метрика | До (haystack) | После (FastBM25) |
|---|---:|---:|
| Все метрики качества | — | **идентичны** (0 отличий по всем полям) |
| Этап BM25, медиана | 0.1976 с | **0.0015 с** (−132×) |
| Total, медиана | 0.4032 с | 0.1597 с (−2.5×) |
| Total, p95 | 0.7315 с | 0.1976 с (−3.7×) |

## Оптимизация 2: batch CrossEncoder (принята, скромный эффект)

`batch_cross_encoder: true` — дедупликация пар и один batched forward вместо
последовательных вызовов. На holdout: качество побайтово идентично stable;
reranking mean 0.157 → 0.107 с (−32%), медиана без изменений (0.053 с),
p95 total 0.852 → 0.643 с. На GPU miniLM уже быстрый, выигрыш в основном в хвосте.
Эквивалентность batched forward на синтетическом ranker'е показана ранее
(см. tests/test_performance.py).

## Оптимизация 3: перенос embedding/reranking/BGE на GPU (принята ранее)

reranking: 0.744 с (CPU) → 0.053 с (CUDA), −14×. Подробности и smoke-тесты:
`reports/retrieval_v3/cuda_smoke.json`, `cuda_qwen_smoke.json`.

## Что не давало эффекта (отрицательные результаты)

- Exact-query embedding cache: holdout не содержит повторов запросов
  (duplicate rate 0), кэширование повторов бесполезно; не внедрялось.
- Увеличение бюджета контекста и min-subtask selection: нулевой эффект на
  качестве (см. 03_coverage_optimization.md) — latency не трогали.
- BGE-M3 E2 на GPU: sparse-стадия 1.3+ с на корпусе 4735 фрагментов —
  медленнее всего пайплайна при худшем ER@6 на MultiDoc2Dial. Не используется
  в V3-Final.

## Итоговая latency V3-Final (stable + batch_ce + FastBM25, pool 20)

| Сплит | Медиана, с | p95, с | Против stable CUDA |
|---|---:|---:|---|
| internal holdout (`v3_holdout_finalperf`) | 0.130 | 0.506 | 0.167 / 0.852 |
| internal test (`v3_test_finalperf`) | 0.150 | 0.370 | 0.141 / 0.342 |
| MultiDoc2Dial 300 (`v3_cuda_multidoc_finalperf`) | 0.193 | 0.378 | coverage: 0.529 / 0.98 |
| LegalBench CUAD 200 (`v3_cuda_legal_finalperf`) | 0.546 | 0.634 | coverage: 0.843 / 0.95 |

Качество V3-Final побайтово равно stable на всех четырёх корпусах (подробнее —
06_final_comparison.md). На CUAD и MultiDoc2Dial основной вклад в ускорение —
FastBM25 (haystack BM25 был доминирующим этапом на длинных документах).

Peak RAM: ~2.5–3 ГБ процесса оценки (E5 + miniLM на GPU; CPU RAM в основном
корпус и индексы). VRAM: ~3.1 ГБ при генерации Qwen (nvidia-smi), retrieval
без Qwen < 2 ГБ.

## Правила инвалидации

- Индекс привязан к fingerprint конфигурации + device; смена устройства или
  модели требует перестройки (`data/index.json` vs `data/index.cpu.json`).
- FastBM25 строится из того же payload индекса при загрузке Retriever —
  расхождение невозможно без изменения индекса.
- Кэшей между запусками не остаётся; benchmark каждый раз холодный по процессу.
