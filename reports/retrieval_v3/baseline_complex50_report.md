# Baseline complex50 (Итерация A): Quality pipeline до внедрения Hierarchical RAG

Дата: 2026-11-13. Датасет: `data/hrag50/hierarchical_complex_qa_50.jsonl`
(50 сложных вопросов: 22 procedure, 18 conditional, 3 comparison, 3 cross_document,
2 decision_tree, 2 roles; 224 required facts, 167 gold clauses, 91 source unit).
Конфигурация Q0 = текущий Quality pipeline без изменений:
`BGE-M3 (dense+sparse) → weighted RRF → bge-reranker-v2-m3 → adaptive selection
(top_k/protected/coverage) → Qwen2.5-3B` (`configs/retrieval_bge_adaptive_rerank.yaml`).

Прогоны: `reports/retrieval_experiments/complex50/Q0_baseline` (полные traces:
кандидаты до/после reranking, итоговый контекст, токены, сырой ответ LLM, цитаты),
`O1_oracle` (LLM получает все эталонные evidence). Evaluator:
`scripts/evaluate_complex_rag.py`. Тест A (rag100) — воспроизводимость
подтверждена ранее (`08_audit_baselines.md`, побайтовое совпадение).

## Метрики retrieval по стадиям (50 вопросов)

| Стадия | Doc Recall | Unit Recall | Clause Recall | Fact Coverage | All Evidence Found |
|---|---:|---:|---:|---:|---:|
| RRF top-20 | 1.000 | 0.877 | 0.855 | 0.824 | 0.640 |
| Reranked top-20 | 1.000 | 0.877 | 0.855 | 0.824 | 0.640 |
| Selected (LLM context) | 1.000 | 0.799 | **0.759** | **0.746** | **0.420** |

**Selection теряет ~10 пунктов покрытия**: доказательства есть среди 20 кандидатов,
но не входят в 6 слотов контекста. Это главный retrieval-дефект baseline.

## Метрики генерации

| Конфиг | Step Recall | Complete@all | False Abstention | Unsupported Quote Rate |
|---|---:|---:|---:|---:|
| Q0 (реальный контекст) | 0.461 | 0.080 (4/50) | 0.060 | 0.337 |
| O1 (oracle-контекст) | 0.636 | 0.140 (7/50) | 0.020 | 0.000 |

Latency: retrieval медиана 2.26 с, генерация 0.71 с, контекст ≈ 658 токенов.

## Декомпозиция потерь (что ограничивает качество)

1. **Selection: −9,6 п.п. clause coverage** (0.855 → 0.759). 13 вопросов с потерей
   > 0.15, примеры: HQ012 (rrf 1.00 → sel 0.50), HQ037 (0.57 → 0.14),
   HQ049 (0.50 → 0.17 → insufficient). Это целевая зона H1 (parent expansion):
   доказательство найдено, но вытеснено из контекста.
2. **Retrieval→ответ: −17,5 п.п. step recall** (Q0 0.461 против O1 0.636 при
   идеальном контексте) — суммарный эффект selection и работы LLM с контекстом.
3. **Генерация: −36,4 п.п. от идеала** (O1 0.636 → 0 при абсолютном потолке 1.0):
   даже со всеми доказательствами LLM покрывает только 2/3 обязательных фактов
   и лишь 14% ответов полные. 6 вопросов с полным покрытием в контексте, но
   провалом генерации (HQ004, HQ006, HQ013, HQ014, HQ017, HQ028 — step < 0.5).

## Полные ответы (Complete@all)

HQ012 (conditional), HQ022 (decision_tree), HQ030 (procedure), HQ033 (roles).

## Абсолютные отказы

3 ложных отказа (HQ049 + 2 при частичном покрытии); oracle снижает до 1.

## Сплиты

Оригинальный сплит протекает: **26 gold clauses пересекаются между dev и test**.
Построен grouped-сплит (`data/hrag50/hierarchical_complex_qa_50_grouped.jsonl`,
18 связных групп по общим clauses, test 35 / dev 15, 0 пересечений).
Baseline по сплитам: test (n=35) clause 0.752 / step 0.457; dev (n=15) clause 0.776 /
step 0.470 — близко, grouped-сплит используем для финальной проверки.

## Выводы итерации A (до внедрения)

1. Качество ответа на сложных процедурах низкое: Step Recall 0.461,
   Complete@all 0.08. Цель плана +10 п.п. — существенный, но достижимый вызов.
2. Потери делятся поровну: selection (фиксится H1/H2 — parent expansion и
   связанные пункты) и генерация (фиксится H5/G1 — проверяемая генерация и
   более сильная LLM). Oracle показывает: идеальный retrieval поднимет
   Step Recall только до 0.636 — одним retrieval'ом цель не достигнуть.
3. Задокументированные traces позволяют провести H1-абляцию немедленно.

## Воспроизводимость

`python scripts/evaluate_complex_rag.py --config configs/retrieval_bge_adaptive_rerank.yaml
--index-path data/experiment_indexes/internal/f08c5dd40c32277b/index.json
--split all --name Q0_baseline --llm` (llama-server CUDA на :8080);
oracle: `--oracle`. Промпт зафиксирован (`navigator/answer.py`, sha в traces).
