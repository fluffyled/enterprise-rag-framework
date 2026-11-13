# Этап 4 — нейросетевой reranking (bge-reranker-v2-m3)

Гипотеза: часть ошибок BGE связана с порядком релевантных фрагментов, а не с
их отсутствием среди кандидатов.

## Реализация

- `navigator/backends.py:BgeV2M3RerankingBackend` — CrossEncoder
  `BAAI/bge-reranker-v2-m3` (ревизия `953dc6f6`, `models/reranker_bge_v2_m3/`,
  залочено в `models.lock.json`). Мультилингвальный (русский включён),
  batch inference, VRAM ≈ 2.3 ГБ, CUDA.
- Интерфейс тот же (`predict`/`rerank`) — индекс BGE переиспользуется без
  перестройки (reranker в индекс не входит).
- Конфиги: `configs/retrieval_bge_rerank.yaml` (top_k),
  `configs/retrieval_bge_rerank_protected.yaml` (+ protected coverage).
- Тесты: `tests/test_backends.py` (+2 фейковых теста); всего 64/64.

## Результаты

### LegalBench CUAD (n=200, paired bootstrap)

| Конфиг | ER@6 | AEH@6 | Δ ER@6 vs E2 [95% CI] | Медиана, с |
|---|---:|---:|---|---:|
| BGE E2 (mMiniLM) | 0.2127 | 0.165 | — | 0.575 |
| BGE adaptive (этап 3) | 0.3566 | 0.285 | +0.144 [+0.090, +0.199] | — |
| **BGE + bge-reranker** | **0.4510** | **0.380** | **+0.238** [+0.175, +0.299] (65/9) | 0.812 |
| BGE + reranker + protected | 0.4400 | 0.365 | +0.227 | 0.865 |

### MultiDoc2Dial (n=300)

| Конфиг | ER@6 | Δ vs E2 [95% CI] | Медиана, с |
|---|---:|---|---:|
| BGE E2 | 0.6567 | — | 1.519 |
| BGE adaptive | 0.6600 | +0.003 | — |
| **BGE + bge-reranker** | **0.7300** | **+0.073** [+0.033, +0.113] (32/10) | 1.210 |

### rag100 test (n=74, selected)

| Конфиг | Doc H@1 | Unit H@1 | Unit H@5 | Unit MRR | Needle | Медиана, с |
|---|---:|---:|---:|---:|---:|---:|
| BGE E2 | 0.946 | 0.797 | 0.932 | 0.858 | 86/92 | 0.776 |
| BGE + bge-reranker | 0.905 | 0.797 | 0.946 | 0.857 | 85/92 | 1.084 |
| BGE + reranker + protected | 0.905 | 0.797 | 0.946 | 0.859 | 86/92 | 1.111 |

На rag100 сильный reranker **нейтрален** (5 продвижений / 3 потери ранга,
включая 2 потери rank-1: Q072, Q074, Q077) — mMiniLM уже хорош на русских
регламентах; doc H@1 просел 0.946→0.905. На CUAD/mdb — огромный прирост.

## Candidate → Final анализ (per-query traces)

| Эксперимент | ok | candidate_miss | rerank_lost | selection_miss |
|---|---:|---:|---:|---:|
| CUAD E2 | 33 | 0 | 0 | 167 |
| CUAD + bge-reranker | 76 | 0 | 0 | 124 |
| mdb E2 | 197 | 12 | 0 | 91 |
| mdb + bge-reranker | 219 | 12 | 0 | 69 |

- Candidate generation почти не ошибается (CUAD: 0/200): **все ошибки — этап
  ранжирования/отбора**, поэтому более сильный reranker и даёт главный прирост.
- mdb: 12 вопросов (4%) — candidate miss, reranker их не лечит (подтверждение
  принципа: reranker не восстанавливает отсутствующие фрагменты).
- Protected поверх сильного reranker'а ничего не добавляет (0.4400 < 0.4510
  на CUAD) — при сильном ранжировании защита top-2 избыточна.

## Затраты

- VRAM: +2.3 ГБ (bge-m3 + reranker-v2-m3 ≈ 4.5 ГБ суммарно, лимит 8 ГБ OK).
- Latency: медиана 1.08–1.23 с/вопрос против 0.78–1.52 у E2 — в пределах нормы.
- Прирост качества (+0.24 ER@6 на CUAD, +0.073 на mdb) многократно окупает
  дополнительные ~0.3 с и 2.3 ГБ VRAM.

## Выводы этапа 4

1. **bge-reranker-v2-m3 принят** как основной reranker для quality-сценария:
   значимый прирост на CUAD и MultiDoc2Dial, нейтрален на rag100.
2. Protected поверх него не нужен — сильное ранжирование делает защиту избыточной.
3. Ошибки сосредоточены на этапе отбора/ранжирования, не candidate generation —
   дальнейшие улучшения искать в selection и span-гранулярности, а не в recall
   кандидатов.
4. Кандидат в Balanced/Quality конфигурации этапа 7: **BGE + bge-reranker**;
   открытый вопрос — совместимость с adaptive (этап 5/7).

## Изменённые файлы

- `navigator/backends.py` (BgeV2M3RerankingBackend), `models.lock.json`,
  `configs/retrieval_bge_rerank{,_protected}.yaml`, `tests/test_backends.py`,
  `scripts/evaluate_rag100.py` (2 конфига);
- прогоны: `rag100_stage4.json`, `v4_{cuad,mdb}_bge_rerank{,_protected}`,
  `v4_stage4/{cuad,multidoc}/`.
