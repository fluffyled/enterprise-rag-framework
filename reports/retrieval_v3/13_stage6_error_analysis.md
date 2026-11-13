# Этап 6 — единый error-analysis pipeline

## Реализация

`scripts/error_analysis_pipeline.py` — единая классификация ошибочных вопросов
по этапу возникновения (таксономия плана, без специальных правил под конкретные
вопросы rag100):

1. `retrieval_miss` — gold-документа нет среди кандидатов;
2. `unit_miss` — документ найден, gold source-unit не найден;
3. `ranking_error` — unit найден, но слишком низко (не top-6);
4. `selection_error` — unit был в кандидатах top-6, удалён селектором;
5. `generation_error` — информация в контексте, LLM ответила неправильно;
6. `citation_error` — ответ верный, ссылка неверная;
7. `false_abstention` — ответ существует, модель отказалась;
8. `unsupported_answer` — ответ не подтверждён контекстом (включая ответы
   на неотвечаемые вопросы).

Вход: end-to-end per_query_results (candidate_all/context_all флаги, статусы)
+ predictions candidates/selected для retrieval-стадий. Выход: `error_analysis.json`
+ `.md` на эксперимент.

## Результаты: rag100 test (80 вопросов), end-to-end

| Конфиг | ok | retrieval_miss | selection_error | generation_error | false_abstention | unsupported_answer |
|---|---:|---:|---:|---:|---:|---:|
| B0 | 63 | 6 | 0 | 6 | 3 | 2 |
| E2 | 63 | 4 | 0 | 8 | 4 | 1 |
| ADAPT | 62 | 4 | 0 | 8 | 4 | 2 |
| **RERANK** | **66** | 4 | 1 | 5 | 3 | 1 |

Детализация по вопросам: `reports/retrieval_v3/end_to_end/rag100/*/error_analysis.md`.

## Интерпретация

1. **RERANK доминирует**: 66 ok против 62–63; меньше generation-ошибок (5 против
   6–8) — лучший контекст снижает и ошибки LLM.
2. B0 проигрывает по retrieval_miss (6 против 4) — E5-индекс хуже находит
   нужный документ на вопросах с перефразом (согласуется с Unit MRR 0.805 vs 0.858).
3. Остаток ошибок RERANK: 4 retrieval_miss (включая Q096 — табличный юнит без
   текстовой привязки в нашем чанкинге), 1 selection_error, 5 generation_error
   (LLM выбирает не те предложения при верном контексте), 3 false_abstention,
   1 unsupported_answer.
4. Точки роста по убыванию эффекта: (a) generation-стадия — 5–8 ошибок,
   фрагментарные цитаты, ложные отказы; (b) retrieval 4–6 (таблицы, span-уровень);
   (c) selection — почти исчезающий класс.

## Вывод этапа 6

Единый pipeline работает на всех конфигурациях end-to-end и сопоставим с
retrieval-таблицей (08). Главный оставшийся класс ошибок — генерация
(выбор предложений и калибровка отказа), а не retrieval: подтверждает вывод
Oracle Context этапа 5 v3.
