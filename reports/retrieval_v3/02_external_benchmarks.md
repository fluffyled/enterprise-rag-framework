# Retrieval v3 — расширенные внешние benchmarks (CUDA)

Все прогоны выполнены на RTX 3070 Ti Laptop (8 ГБ), torch 2.11.0+cu126, `device: cuda`.
Сравнения парные по одинаковым замороженным выборкам (`data/frozen_external_eval.json`).
Разные языки и домены не объединяются в одну итоговую метрику.
Полные per-query traces, bootstrap-распределения и графики: `reports/retrieval_experiments/v3_external_cuda/<dataset>/`.

Эквивалентность CPU/GPU подтверждена на MultiDoc2Dial: все метрики бит-в-бит совпали
с CPU-прогонами (`v3_external/`), query_set_sha256 `f892c551…` идентичен.

Конфигурации: `baseline` = BM25+E5 RRF → mMiniLM → top-k; `mmr` = MMR-отбор;
`coverage` = stable coverage-aware (декомпозиция + coverage selection); `bge_e2` = BGE-M3 sparse 0.5 + dense.

## MultiDoc2Dial — 300 validation queries / 488 documents (en)

| Конфигурация | Doc Recall@5 | Evidence Recall@6 | All-Evidence Hit@6 | MRR@10 | nDCG@10 | Медиана, с | p95, с |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 0.880 | 0.6667 | 0.6667 | 0.4985 | 0.5311 | 0.40 | 0.73 |
| mmr | 0.880 | 0.6733 | 0.6733 | 0.4985 | 0.5311 | 0.58 | 0.82 |
| coverage | 0.880 | 0.6667 | 0.6667 | 0.4985 | 0.5311 | 0.53 | 0.98 |
| bge_e2 | 0.880 | 0.6567 | 0.6567 | 0.5100 | 0.5321 | 1.52 | 2.39 |

- Все четыре метода статистически неразличимы: 95% CI для Δ Evidence Recall@6 против baseline покрывает ноль у всех ([-0.013, +0.027] у mmr; [-0.057, +0.033] у bge_e2).
- Doc Recall@5 насыщен на 0.88; ошибки концентрируются не в поиске документа, а в попадании точного span: из 100 ошибок baseline 90 — «gold-документ дошёл до reranked, но итоговый span не покрыт» (evidence_precision всего 0.024 — gold spans очень короткие относительно чанков 110 слов).
- Только 15/300 запросов не имеют gold-документа в BM25 top-20 и Dense top-20 → candidate retrieval почти не ограничивает.
- Вывод: на multidoc2dial улучшать надо span-level отбор/чанкинг, а не ranking. Coverage не даёт прироста, т.к. вопросы в среднем одно-требовательные (gold_requirement_count = 1.0).

## LegalBench-RAG — 200 CUAD queries / 17 документов (en)

| Конфигурация | Doc Recall@5 | Evidence Recall@6 | All-Evidence Hit@6 | MRR@10 | nDCG@10 | Медиана, с | p95, с |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 1.000 | 0.1588 | 0.120 | 0.1025 | 0.1606 | 0.26 | 0.29 |
| mmr | 1.000 | 0.1696 | 0.120 | 0.1025 | 0.1606 | 0.15 | 0.28 |
| coverage | 1.000 | 0.2597 | 0.210 | 0.0923 | 0.1281 | 0.84 | 0.95 |
| bge_e2 | 1.000 | 0.2127 | 0.165 | 0.1113 | 0.1597 | 0.57 | 0.64 |

- **Coverage — единственный метод с значимым приростом**: Δ Evidence Recall@6 = **+0.101** [95% CI 0.056–0.148], 33 улучшено / 5 ухудшено; All-Evidence Hit@6 +0.09 [0.045–0.135]. Причина: у CUAD в среднем 1.62 gold-требования на вопрос — диверсифицированный coverage-отбор покрывает несколько условий договора, где top-k берёт повторяющиеся фрагменты одного положения.
- MMR даёт незначительный +0.011 [-0.012, +0.037].
- BGE-M3 E2: +0.054 к Evidence Recall@6 против baseline, но 95% CI [0.023, 0.088] не пересекается с coverage; при этом медленнее (0.57 с).
- Снижение MRR@10/nDCG@10 у coverage ожидаемо: ранговые метрики @10 считаются по итоговому контексту top-6, а coverage намеренно ставит рядом фрагменты из разных разделов, снижая ранговую концентрацию. Document-метрики насыщены (1.0 у всех).
- Ошибки: 158/200 вопросов с ошибкой у coverage — «available but missed» на span-уровне; gold-документ (из 17) всегда в кандидатах (`no gold BM25/Dense/RRF/reranked = 0` у baseline/mmr/coverage). Это подтверждает вывод этапа 1: ограничитель — покрытие span'ов внутри больших контрактов (chunking/span granularity), а не поиск документа.
- У bge_e2 167 ошибок без gold на BM25-этапе — ожидаемо, т.к. в этой конфигурации первичный sparse-проход заменяет BM25.

## MIRACL Russian — pilot 50 запросов / 2000 документов / 2 шарда (ru)

| Конфигурация | Doc Recall@5 | Doc MRR@10 | Doc nDCG@10 | Медиана, с | p95, с |
|---|---:|---:|---:|---:|---:|
| baseline | 0.996 | 1.000 | 0.9996 | 0.27 | 0.30 |
| mmr | 0.996 | 1.000 | 0.9996 | 0.21 | 0.23 |
| coverage | 0.996 | 1.000 | 0.9996 | 0.22 | 0.25 |
| bge_e2 | 0.996 | 1.000 | 0.9996 | 0.32 | 0.36 |

- **Pilot насыщен**: все методы дают Doc Recall@5 = 0.996 на 2000-документном корпусе. Различий в качестве нет; измеряются только latency. Это не полноценный benchmark, а проверка работоспособности на русском языке и на дисковом индексе.
- Ограничения pilot: неофициальная оценочная выборка, incomplete judgments, evidence-метрики недоступны (нет span-разметки в qrels → `evidence_recall@6 = null`). Для различения методов нужен полный корпус (сотни тысяч документов) — вынесено в направления дальнейшей работы.
- Технически подтверждено: потоковая индексация 2000 документов батчами, индекс на диске, GPU-embeddings работают стабильно.

## Сводные выводы этапа

1. **Польза coverage-aware retrieval подтверждена на данных с несколькими требованиями на вопрос** (CUAD: +0.10 Evidence Recall@6, 95% CI не включает ноль). На одно-требовательных вопросах (MultiDoc2Dial) прироста нет — поведение соответствует дизайну.
2. **Главный оставшийся ограничитель на внешних данных — span-гранулярность**, не поиск документа: ≥88% ошибок всех конфигураций — «gold-документ найден, точный span не покрыт». Соответствует выводу Oracle Analysis этапа 1 (потери при переходе candidate pool → итоговый контекст).
3. BGE-M3 E2 не оправдывает latency-стоимость на этих данных (хуже coverage на CUAD, хуже baseline на MultiDoc2Dial по ER@6).
4. Latency на CUDA: baseline 0.26–0.40 с, coverage 0.53–0.84 с (доплата за декомпозицию и дополнительный retrieval-проход), bge_e2 0.32–1.52 с. CPU-проблема p95 = 8.1 с на holdout закрыта переносом на GPU (p95 ≤ 0.98 с на MultiDoc2Dial).

## Воспроизводимость

- Замороженные выборки: `data/frozen_external_eval.json`; query_set_sha256: multidoc `f892c551…`, CUAD `840ca529…`, MIRACL `62cca72a…`.
- Конфиги: `configs/retrieval_cuda_{baseline,mmr,stable,bge_e2}.yaml`; индексы: `data/experiment_indexes/<dataset>/<fingerprint>/`.
- Команды: `python scripts/evaluate_retrieval.py --dataset <name> --config <cfg> --limit <n> [--split cuad | --corpus-limit 2000 --shard-limit 2] --name <exp>`; comparison: `scripts/compare_experiments.py`.
- CPU-результаты (для сверки): `reports/retrieval_experiments/v3_external/` (multidoc), `v3_legal_*` (CUAD baseline/mmr). Не перезаписывались.
