# Финальный отчёт: Accuracy-first Hierarchical RAG (complex50 + регрессии)

Дата: 2026-11-14. Платформа: RTX 3070 Ti 8 ГБ, torch 2.11.0+cu126,
Qwen2.5-3B q4_k_m (llama.cpp CUDA). Все прогоны воспроизводимы (seed 42,
конфиги в git, traces в `reports/retrieval_experiments/`). Gold-разметка
только в evaluation; параметры не подбирались на test (dev + CUAD как
validation; итоговые конфиги не имели настраиваемых параметров).

## 1. Матрица Q0–O1 на complex50 (50 вопросов; E1/E2 — retrieval-only)

| Конфигурация | Clause Recall | Fact Coverage | All Found | Step Recall | Complete@all | False Abst | Unsupported |
|---|---:|---:|---:|---:|---:|---:|---:|
| Q0 baseline (BGE+bge-reranker+adaptive) | 0.759 | 0.746 | 42% | 0.461 | 8% | 6% | 0.337 |
| H1 + parent expansion | 0.914 | 0.912 | 68% | 0.426 | 10% | 4% | 0.365 |
| H2 + related clauses | 0.914 | 0.912 | 68% | 0.429 | 6% | 4% | 0.362 |
| H3 + multi-hop (decomposition) | 0.925 | 0.924 | 76% | 0.306 | 4% | 0% | 0.377 |
| H4 + iterative (≈H3) | 0.927 | 0.928 | 78% | 0.360 | 4% | 0% | 0.350 |
| E1/E2 + enrichment (doc2query) | 0.927 | 0.928 | 78% | — | — | — | — |
| **H1 + H5 verified generation** | 0.914 | 0.912 | 68% | **0.558** | **22%** | 14% | 0.160 |
| O1 oracle + обычная генерация | 1.000 | 1.000 | 100% | 0.636 | 14% | 2% | 0.000 |

## 2. Регрессионные проверки (по решению — точечно, целевой датасет основной)

| Корпус | Метрика | Quality (Q0) | H1 parent | H3 multi-hop |
|---|---|---:|---:|---:|
| rag100 (92 отвеч.) | Needle Recall | 86/92 | 86/92 | 86/92 |
| rag100 | Gold-doc hit@6 | 92/92 | 92/92 | 92/92 |
| rag100 | Медиана | 0.78 с | 2.63 с | 21.5 с |
| CUAD (n=200) | ER@6 | 0.4510 | 0.4570 | — |

rag100: деградации качества H1/H3 нет (needle и doc-hit идентичны Q0),
цена — latency ×3,4 / ×27. CUAD H1 слегка выше Q0 (0.4570 против 0.4510).
Полная регрессионная матрица (mdb, cuad_h3) не выполнялась по решению:
целевой датасет complex50 — основной критерий. Ограничение зафиксировано.

## 3. Главные выводы

1. **Поиск доведён до потолка**: H3/H4 clause recall 0.927 при oracle 1.000;
   остаток — 2 непарсируемых места и редкие hard-кейсы. Дальнейшие инвестиции
   в retrieval на этом корпусе не окупаются.
2. **Ключевой результат исследования — H5 (проверяемая генерация)**:
   единственный подход, конвертировавший покрытие в качество ответа
   (Step Recall 0.558, Complete@all 22% — выше oracle+plain 14%). Механика:
   структурированный план по evidence-блокам + детерминированная верификация
   (стеммы + цифры) отсекает неподтверждённое (unsupported 0.16 против 0.34).
3. **Отрицательные результаты (зафиксированы)**: H2 related clauses (21 ребро
   ссылок в корпусе — нечего расширять); H4 iterative (раунд-2 не срабатывает
   при лояльном пороге); E1/E2 enrichment (покрытие уже насыщено, 0 изменений
   на 11 непокрытых вопросах); обычная генерация на больших контекстах
   деградирует (0.461 → 0.306 при росте контекста 658→3050 токенов).
4. **Генерация — следующий рычаг**: oracle-потолок текущей связки ~0.64 step
   recall с идеальным контекстом; формулировка инструкций требует модели
   сильнее 3B (G-эксперименты отложены: 14B+ не влезает в 8 ГБ VRAM —
   Kaggle/сервер с предложением пользователя).

## 4. Рекомендуемые конфигурации

- **Complex/Quality**: `retrieval_h1_parent.yaml` (retrieval) + `--generation-mode verified` (H5). Ожидаемый Step Recall ≈ 0.56, Complete@all ≈ 22%, все шаги с пунктами-источниками.
- **Mixed/Balanced**: `retrieval_bge_adaptive_rerank.yaml` (Quality v3) — лучший компромисс на простых вопросах (rag100 Unit MRR 0.858, E2E 0.87).
- **Saturated retrieval для downstream**: `retrieval_h4_iterative.yaml` (clause 0.927) — когда потребитель контекста умеет работать с 3k токенами.

## 5. Ограничения

- H5: 14% ложных отказов, ~56 с генерация/вопрос (16k контекст); шаги — фрагменты, не полированные инструкции.
- H3/H4: 9 с/вопрос (multi-hop ×3–5 проходов + LLM-планировщик).
- Один аннотатор ручных проверок; judge (Qwen-3B) ненадёжен (согласие 38%) — не использовался для выборов.
- Enrichment-инфраструктура готова, но эффект на данном корпусе нулевой; пересмотреть на корпусе с терминологическим зазором.

## 6. Артефакты

- Код: `navigator/parent_expansion.py`, `navigator/multi_hop.py`, `navigator/verified_answer.py`, `navigator/enrichment_search.py`, `scripts/build_clause_store.py`, `scripts/build_enrichment.py`, `scripts/evaluate_complex_rag.py`, конфиги `retrieval_{h1_parent,h2_related,h3_multihop,h4_iterative,e1_questions,e2_facts}.yaml`.
- Данные: `data/clauses/clauses.json` (439 пунктов), `data/enrichment/` (322 факта + 949 вопросов + manifest), grouped-сплит `data/hrag50/*_grouped.jsonl`.
- Отчёты итераций: `reports/retrieval_v3/15…19`, baseline `baseline_complex50_report.md`; traces: `reports/retrieval_experiments/complex50/*`.
