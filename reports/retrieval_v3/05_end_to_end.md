# Retrieval v3 — end-to-end оценка (retrieval → Qwen2.5-3B → цитаты)

## Установка

- Сплиты: `test` (20 вопросов, все отвечаемые — независимый, до этого не использовался)
  и `holdout` abstention-подвыборка (3 неотвечаемых вопроса).
- LLM: Qwen2.5-3B-Instruct q4_k_m через llama.cpp CUDA (`tools/llama-cuda`,
  `-ngl 999`, контекст 8192, `-t 4`). Endpoint `127.0.0.1:8080`, ничего не уходит наружу.
- Единые для всех вариантов: prompt (sha256 `dfcfc0ab…`), JSON-схема ответа,
  настройки генерации (temperature из `navigator/answer.py`, без изменений между вариантами).
  Меняется только retrieval.
- Варианты: **B0** = baseline CUDA, **V2** = stable coverage CUDA,
  **V3F** = V3-Final (coverage + pool 40 + batch CE + FastBM25), **ORACLE** = руками
  подтверждённые gold spans вместо retrieval (offline-эксперимент, gold в рабочий поиск не попадает).
- Метрики — прокси на точном пересечении цитат с gold spans
  (`semantic_citation_review` и ручные поля оставлены `null`: второй аннотатор не привлекался,
  внутренние документы наружу не отправлялись). Все числа требуют семантической проверки перед продакшен-выводами.

## Результаты: test (20 отвечаемых)

| Вариант | Success | Citation P | Citation R | Unsupported quotes | Медиана total, с (gen) | Failure categories |
|---|---:|---:|---:|---:|---:|---|
| B0 | 0.90 | 0.807 | 0.925 | 10 | 0.88 (0.65) | evidence_absent_from_candidates ×1, false_abstention ×1 |
| V2 | 0.90 | 0.808 | 0.925 | 9 | 0.65 (0.41) | evidence_absent_from_candidates ×1, evidence_present_but_not_selected_by_llm ×1 |
| V3F | 0.90 | 0.833 | 0.925 | 8 | 0.72 (0.41) | evidence_not_selected ×1, evidence_present_but_not_selected_by_llm ×1 |
| ORACLE | **0.85** | **1.000** | 0.875 | 0 | 0.30 (0.30) | evidence_present_but_not_selected_by_llm ×1, false_abstention ×2 |

Procedure completeness (procedure-вопросы) = 1.0 у всех вариантов.

## Разбор ошибок по вопросам

| Вопрос | B0 | V2 | V3F | ORACLE | Интерпретация |
|---|---|---|---|---|---|
| test-014 | retrieval: доказательство отсутствует уже в кандидатах | то же | selection: доказательство было в кандидатах, но не выбрано | отвечен, но LLM не использовал доступный gold | Самый тяжёлый вопрос сплита (retrieval ER@6 = 0.5 у всех конфигураций). V3F довёл evidence до стадии selection — частичный прогресс пайплайна, success не изменился из-за citation completeness |
| test-020 | LLM отказалась при достаточном контексте (false abstention) | ответ верный по смыслу, цитирует не всё (LLM-side) | как V2 | — | Разные режимы ошибки: B0 теряет доказательства → abstain; V2/V3F находят, но LLM не цитирует полностью |
| test-003 | ок | ок | ок | LLM не использовала gold из идеального контекста | Чистая generation-ошибка: видит правильный фрагмент, не берёт цитату |
| test-004, test-018 | ок | ок | ок | false abstention при идеальном контексте | Калибровка отказа Qwen: сырые gold spans без окружения читаются как недостаточные |

## Oracle Context Experiment (ключевой результат)

Идеальный контекст даёт **citation precision 1.0** (Qwen не фабрикует цитаты,
когда видит ровно нужные фрагменты), но **success падает до 0.85**: два ложных
отказа на изолированных gold spans без контекста окружения и одна неиспользованная цитата.

Выводы:
1. Потолок текущей связки retrieval+LLM определяется **генерацией/калибровкой отказа**,
   а не retrieval: даже идеальный контекст не даёт 1.0.
2. Прокси-success 0.90 у B0/V2/V3F при 0.85 у ORACLE означает, что на test-сплите
   retrieval-различия в end-to-end не проявляются: все варианты терпят 2 ошибки
   (одна общая тяжёлая retrieval-ошибка test-014 + одна ошибка генерации).
3. Направление «расширение gold spans окружением» для oracle-режима и дообучение/
   промпт-настройка калибровки abstain — отдельное направление (вне scope v3,
   согласно плану архитектура ответов Qwen не менялась).

## Abstention (holdout, 3 неотвечаемых вопроса)

| Вариант | Abstention P | Abstention R | False abstentions (на отвечаемых) |
|---|---:|---:|---:|
| B0 | 1.0 | 1.0 | 0 |
| V2 | 1.0 | 1.0 | 0 |
| V3F | 1.0 | 1.0 | 0 |
| ORACLE | 1.0 | 1.0 | 0 |

На неотвечаемых вопросах все конфигурации корректно отказываются (3/3), ложных
отказов на отвечаемых holdout-вопросах нет. Положительный эффект coverage-контекста:
V2/V3F на test-020 отвечают там, где B0 отказался, — но с неполной цитатой, что
прокси-success не засчитывает.

## Latency end-to-end (медиана)

| Вариант | Retrieval, с | Generation, с | Total, с |
|---|---:|---:|---:|
| B0 | 0.23 | 0.65 | 0.88 |
| V2 | 0.24 | 0.41 | 0.65 |
| V3F | 0.31 | 0.41 | 0.72 |
| ORACLE | 0.0 | 0.30 | 0.30 |

Разброс generation (0.30–0.65 с) отражает длину контекста и ответа; V2/V3F
генерируют быстрее B0 за счёт более компактного контекста (coverage selection
убирает дубли).

## Ограничения

- n=20 (test) и n=3 (abstention) — мало для статистики; выводы качественные.
- Метрики — literal-overlap прокси; семантическая проверка цитат и ручная
  разметка корректности ответа не выполнялись (поля `manual_*` = null).
- Один аннотатор разметки сплитов; расхождения оценок не фиксировались.
- Внутренние документы в облачные оценочные сервисы не отправлялись.

## Воспроизводимость

`python scripts/evaluate_end_to_end_v3.py --split test --experiment B0=configs/retrieval_cuda_baseline.yaml
--experiment V2=configs/retrieval_cuda_stable.yaml --experiment V3F=configs/retrieval_v3_final.yaml
--experiment ORACLE=oracle` (llama-server CUDA на 127.0.0.1:8080 предварительно;
abstention: `--split holdout --only-unanswerable`).
Результаты: `reports/retrieval_v3/end_to_end/{test,holdout_abstention}/`.
