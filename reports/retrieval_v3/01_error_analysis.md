# Retrieval v3 — детальный аудит ошибок

## Проверка метрики

- reranked candidates before final context selector.
- final selected context.
- deduplicated document ranking of candidates.
- any positive character overlap counts as evidence hit; coverage separately measures fraction.
- Gold spans используются только в offline-анализе и не передаются в рабочий retrieval.

## Baseline и stable по вопросам

| Question ID | Answerable | Baseline Recall | Stable Recall | Изменение | Причина по gold groups |
|---|---|---:|---:|---:|---|
| holdout-001 | True | 0.0000 | 0.0000 | 0.0000 | Fusion Error |
| holdout-002 | True | 0.5000 | 0.5000 | 0.0000 | Candidate Retrieval Error |
| holdout-003 | False | — | — | — | не входит в evidence-знаменатель |
| holdout-004 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-005 | True | 0.0000 | 0.3333 | 0.3333 | Candidate Retrieval Error |
| holdout-006 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-007 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-008 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-009 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-010 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-011 | True | 0.0000 | 0.0000 | 0.0000 | Candidate Retrieval Error, Fusion Error |
| holdout-012 | False | — | — | — | не входит в evidence-знаменатель |
| holdout-013 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-014 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-015 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-016 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-017 | True | 0.0000 | 1.0000 | 1.0000 | дополнительное покрытие после декомпозиции/selection |
| holdout-018 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-019 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-020 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-021 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-022 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-023 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-024 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-025 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-026 | True | 1.0000 | 1.0000 | 0.0000 | нет новой ошибки |
| holdout-027 | False | — | — | — | не входит в evidence-знаменатель |

## Классификация ошибок

| Категория | Количество gold groups |
|---|---:|
| Parsing Error | 0 |
| Chunking Error | 0 |
| Candidate Retrieval Error | 4 |
| Fusion Error | 2 |
| Reranking Error | 0 |
| Selection Error | 0 |
| Decomposition Error | 0 |
| Insufficient Context Budget | 0 |
| Gold Annotation Issue | 0 |

## Доказательства по ошибкам

| Question/group | Категория | BM25 | Dense | RRF | Rerank | Selected | Chunk IDs |
|---|---|---:|---:|---:|---:|---:|---|
| holdout-001/holdout-001-requirement-1 | Fusion Error | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | b97d3d2c5bcf1b354f116b52 |
| holdout-002/holdout-002-requirement-1 | Candidate Retrieval Error | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | b97d3d2c5bcf1b354f116b52 |
| holdout-005/holdout-005-requirement-2 | Candidate Retrieval Error | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 9ad9ebc219de75ba183c2c37 |
| holdout-005/holdout-005-requirement-3 | Candidate Retrieval Error | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 9ad9ebc219de75ba183c2c37 |
| holdout-011/holdout-011-requirement-1 | Candidate Retrieval Error | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | cb1dac4f5fa73ac667d6c2ee |
| holdout-011/holdout-011-requirement-2 | Fusion Error | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 | 23ba16ff911f916692fde8c5 |

## Oracle Analysis

| Сценарий | Recall | All-Evidence Hit |
|---|---:|---:|
| baseline: oracle_a_bm25_dense | 0.8889 | 0.8333 |
| baseline: oracle_b_rrf | 0.8125 | 0.7917 |
| baseline: oracle_c_reranked | 0.8125 | 0.7917 |
| stable: oracle_a_bm25_dense | 0.8889 | 0.8333 |
| stable: oracle_b_rrf | 0.8681 | 0.8333 |
| stable: oracle_c_reranked | 0.8681 | 0.8333 |
| Oracle D: прямой gold при том же бюджете | 1.0000 | 1.0000 |

## Приоритеты

- Candidate Retrieval Error: 4 gold groups; требуется улучшать нахождение кандидатов, а не усложнять selector.
- Fusion Error: 2 gold groups; проверить потерю при top-20 RRF и расширение candidate pool.
- Selection/Budget: 0 / 0; увеличение бюджета по текущим ошибкам не обосновано.
- Stable ухудшил baseline на 0 вопросах: [].
- Oracle использует gold только в offline-отчёте. Прямой Oracle D — потолок метрики, а не рабочий поиск.
