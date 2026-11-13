# Этап 2 — BGE-M3 + защищённый coverage-selection

Гипотеза: BGE-M3 хорошо находит релевантные фрагменты; coverage может улучшить
охват составных вопросов, но не должен вытеснять лучшие результаты.

## Реализация

`navigator/selection.py:select_protected_coverage`, стратегия `protected_coverage`:

1. Кандидаты от BGE-M3 E2 (dense+sparse, weighted RRF) → mMiniLM rerank.
2. Первые `protected_top_p` кандидатов по релевантности резервируются безусловно
   (в пределах token budget) — ранговые метрики single-fact вопросов сохраняются.
3. Остальные слоты заполняются жадно по целевой функции:

   `Score(c) = α·Relevance(c) + β·MarginalCoverage(c,S) − γ·Redundancy(c,S)`

   - Relevance — min-max нормированный rerank score ∈ [0,1];
   - MarginalCoverage — средний прирост покрытия подзадач (матрица нормированных
     cross-encoder скоров по подзадачам правиловой декомпозиции) ∈ [0,1];
   - Redundancy — средний Jaccard по токенам к уже выбранным ∈ [0,1].
   Масштабы сопоставимы, дополнительная нормировка не требуется.
4. Параметры `protected_top_p`, `coverage_alpha/beta/gamma` — в конфигурации
   (`navigator/config.py` defaults: p=2, α=0.5, β=0.3, γ=0.2).

Конфиги: `configs/retrieval_bge_protected.yaml`, `configs/retrieval_bge_coverage.yaml`.
Тесты: `tests/test_protected_coverage.py` (6 тестов: защита top-p, заполнение
по скору, бюджет, обязательность matrix, пустой ввод, регистрация стратегии).
Всего 55/55 тестов зелёные.

## Настройка параметров (только dev, 18 отвечаемых)

Сетка p∈{1,2,3} × β∈{0.3,0.5} (γ=0.2, α=0.5): **все 6 комбинаций дали
идентичные dev-метрики** (docH@1 1.0, unitMRR 0.889, needle 86/92) — dev-вопросы
одно-требовательные, параметры селекции не влияют на выбор. Взяты дефолты p=2,
β=0.3. Вывод: rag100 dev нечувствителен к параметрам coverage; для будущих
настроек нужны многотребовательные validation-данные (CUAD).

## Результаты

### rag100 test (n=74, selected, групповой bootstrap 2000)

| Конфиг | Doc H@1 | Doc MRR | Unit H@1 | Unit H@5 | Unit MRR | Δ Unit MRR vs E2 [95% CI] |
|---|---:|---:|---:|---:|---:|---|
| BGE E2 (base) | 0.946 | 0.970 | 0.797 | 0.946* | 0.858 | — |
| BGE + coverage | 0.784 | 0.886 | 0.527 | 0.946 | 0.725 | **−0.133** [−0.194, −0.062] значимо хуже |
| BGE + protected | 0.946 | 0.970 | 0.797 | **0.960** | **0.863** | +0.005 [0.000, 0.013] без регрессий |

\* unitH@5 E2 = 0.932 (из 08); protected 0.960 — лучшее значение серии.
Needle Recall всех трёх: 86/92. Latency: E2 0.776 с, protected 0.435 с,
coverage 0.464 с (медиана; тот же индекс, порядок прогонов).

### LegalBench CUAD (n=200, paired bootstrap)

| Конфиг | ER@6 | AEH@6 | Δ ER@6 vs E2 [95% CI] |
|---|---:|---:|---|
| BGE E2 | 0.2127 | 0.165 | — |
| BGE + coverage | **0.2755** | **0.220** | **+0.063** [+0.011, +0.112] значимо лучше |
| BGE + protected | 0.2239 | 0.175 | +0.011 [−0.009, +0.033] нейтрально |

### MultiDoc2Dial (n=300, paired bootstrap)

| Конфиг | ER@6 | Δ vs E2 [95% CI] |
|---|---:|---|
| BGE E2 | 0.6567 | — |
| BGE + coverage | 0.6567 | 0.000 |
| BGE + protected | **0.6700** | +0.013 [−0.003, +0.033] (6 улучш./2 ухудш.) |

## Выводы этапа 2

1. **Protected coverage работает как задумано**: устраняет значимое падение
   ранговых метрик plain coverage (−0.133) до нуля, сохраняя небольшой прирост
   покрытия (rag100 unitH@5 0.960 — лучшее; unit MRR 0.863 — лучшее).
2. **На многотребовательных юридических вопросах лучший вариант — BGE + plain
   coverage** (CUAD ER@6 0.2755, значимо лучше E2 +0.063). Protected там
   нейтрален — защита top-2 отнимает слоты у покрытия дополнительных требований.
3. **Универсального победителя нет**: single-fact корпуса → protected/E2;
   multi-requirement → plain coverage. Это прямое обоснование адаптивного
   выбора стратегии (этап 3).
4. Критерий успеха этапа (улучшение покрытия составных вопросов без существенного
   падения Unit H@1/MRR на однофактных) — **достигнут для protected**;
   plain coverage на CUAD — дополнительный значимый результат.

## Изменённые файлы

- `navigator/selection.py` — `select_protected_coverage`, регистрация стратегии;
- `navigator/retrieval.py` — вычисление матрицы для protected_coverage, новые kwargs;
- `navigator/config.py` — defaults p/α/β/γ;
- `configs/retrieval_bge_protected.yaml`, `configs/retrieval_bge_coverage.yaml`;
- `tests/test_protected_coverage.py`;
- `scripts/evaluate_rag100.py` — overrides для сеток;
- прогоны: `v4_{cuad,mdb}_bge_{coverage,protected}`, `rag100_stage2_test.json`,
  `v4_stage2/{cuad,multidoc}/`, `dev_grid_protected.json`.
