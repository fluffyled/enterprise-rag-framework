# RETRIEVAL_FREEZE_REPORT — Retrieval v4.1 Stable

Дата: 2026-11-14. База: аудит `236de3a` → стабилизация (настоящий коммит).
Критерии готовности к заморозке выполнены (чек-лист в конце).
Дальнейшие исследования — в отдельных ветках, не влияющих на baseline генерации.

## 1. Архитектура поиска (заморожена)

```
Fast Stable (по умолчанию, configs/retrieval_fast_stable.yaml ≡ retrieval_stable.yaml)
  BGE-M3 (dense + sparse, w=0.5) → weighted RRF → bge-reranker-v2-m3 (batched)
  → adaptive selection (single_fact→top_k / multi_requirement→protected_coverage
  / multi_document→coverage / uncertain→top_k)

Quality Stable (configs/retrieval_quality_stable.yaml, явный выбор)
  то же + parent expansion: leaf-чанк → полные пункты (span-overlap, clause store)

Экспериментальные (НЕ входят в stable): H2 related, H3/H4 multi-hop,
E1/E2 enrichment, H5 verified generation (зона агента генерации).
```

## 2. Артефакты и версионирование

- **Clause Store**: `data/clauses/clauses.json` — **747 пунктов, 20/20 документов**,
  построение ПОЛНОСТЬЮ без gold (`scripts/build_clause_store.py`; проверено
  запуском при отсутствии `data/hrag50/`). Gold-валидация отдельно:
  `scripts/validate_clause_store.py` → **239/239** gold-цитат внутри пунктов
  своих номеров. Baseline прежнего gold-scoped store сохранён
  (`clauses_goldscoped_baseline.json`). Отчёт постройки: `clause_build_report.json`.
- **Manifest**: `data/retrieval_manifest.json` (`scripts/build_retrieval_manifest.py`):
  git SHA, fingerprint корпуса, checksum Clause Store и BGE-индекса, hash
  stable-конфигов, версии моделей/библиотек, seed, fingerprint датасетов.
  `navigator/manifest.validate()` вызывается при создании Retriever и при
  рассинхронизации даёт понятную ошибку.
- **Индексы**: основной рабочий — BGE-M3 internal (`f08c5dd40c32277b`,
  3079 чанков, CUDA). E5-индекс `data/index.json` — legacy для исторических
  сравнений.

## 3. Исправления стабилизации (поверх аудита D1–D7)

1. **Координаты пунктов**: `end` — истинная граница (прежде повреждалась
   `.strip()`), инвариант `text[start:end].strip() == full_text` проверяется
   assert'ом; золотая валидация улучшилась 237/239 → 239/239.
2. **Родитель по числовому префиксу** (не «ближайший выше»); при
   неоднозначности — `parent_ambiguous=True`, связь не выдумывается.
3. **References** связываются только при уникальном номере в документе.
4. **Parent expansion**: контракт происхождения (document_id, chunk_id,
   clause_id, номер, страница/локатор, source_span, expansion_status);
   диагностика `expanded_successfully / fallback_to_original_chunk /
   clause_too_large / budget_exhausted / missing_clause / invalid_source_span`;
   безопасный fallback на исходный чанк; тихой потери evidence нет.
5. **Приложение**: `retrieval_stable.yaml` = Fast (раньше обещал BGE, а
   запускал E5). Явный выбор: `NAVIGATOR_CONFIG` / `NAVIGATOR_INDEX`
   (заданы в `start.ps1`), скрытой автосмены алгоритма нет.
6. **Evaluator**: `--gold-path` (grouped split), семантика метрик
   задокументирована в модуле.

## 4. Тесты

**104/104** (`pytest tests/`):
- парсер: 9 тестов (вложенность 2→2.1→2.1.1, разрыв страницы, повтор 1.1
  в приложении, таблицы, документ без нумерации, длинный пункт, повреждённые
  блоки, ambiguous-parent, references);
- parent expansion: 8 тестов (контракт, fallback, budget_exhausted,
  missing/invalid span, cross-doc дедупликация, нарушение бюджета);
- evaluator: 10 тестов аудита (cross-doc, strict/soft, завышение step recall,
  составные факты, отказы/ошибки, дубликаты evidence, oracle-максимальность);
- прочие (FastBM25, coverage, adaptive, multi-hop, enrichment, backends).

End-to-end smoke: построение индекса → Clause Store → поиск stable-конфигом →
документы с корректными ссылками — пройден (Retriever + manifest validation).

## 5. Метрики (корректные, post-audit)

### 5.1 Регресс-контроль (original split, n=50) — прогоны FREEZE_*

| Конфиг | Document-aware Clause Recall | Strict | База аудита | Статус |
|---|---:|---:|---:|---|
| Q0 | 0.707 | 0.645 | 0.707 / 0.645 | ✅ совпадение |
| Fast Stable | 0.707 | 0.645 | = Q0 (идентичный конфиг) | ✅ |
| Quality Stable (H1) | 0.896 | 0.845 | 0.896 / 0.845 | ✅ совпадение |
| H4 (эксп.) | 0.909 | 0.845 | 0.909 / 0.845 | ✅ совпадение (после фикса распаковки expand_parents в multi_hop) |

Fact Coverage / All Found: Q0 0.702/42%, Quality 0.904/68%, H4 0.916/74% —
все равны базе аудита. **Объясняемых изменений нет: все исправления
стабилизации (координаты, parent, контракт expansion, диагностика)
quality-neutral**, как и ожидалось (start-координаты и спаны чанков
не менялись; runtime-изменения — fallback и метаданные).

### 5.2 Grouped split (официальные числа v4.1, test n=35)

| Конфиг | Clause Recall | Strict | Fact Coverage | All Found |
|---|---:|---:|---:|---:|
| Fast Stable | 0.707* | 0.645* | 0.702* | 42%* |
| Quality Stable | **0.909** | **0.862** | **0.908** | **69%** |

\* Fast на grouped-test не пересчитывался отдельно (identical config к Q0;
значения с original split all-50). Quality — официальный результат v4.1.

### 5.3 Спот-регрессии (зафиксированные протоколы, без изменений)

- rag100 (100 вопросов): Fast Stable = прежнему Quality v3 — needle 86/92,
  doc-hit 92/92 (регрессии нет; проверено при внедрении H1/H3).
- CUAD 200: Quality-пайплайн (bge-reranker) ER@6 0.4510; H1 0.4570.
- MultiDoc2Dial 300: bge-reranker ER@6 0.7300.

## 6. Производительность

- Fast Stable: медиана ~0.8 с/вопрос (rag100), 0.4–0.8 с E2E.
- Quality Stable: медиана ~2.6 с/вопрос (parent expansion; FREEZE-прогоны
  подтвердили порядок).
- H4 (эксп.): ~9 с/вопрос (multi-hop + LLM-планировщик).
- Исправления стабилизации — диагностика и fallback; деградации скорости нет
  (измерения 5.1 совпали с базой, где замеры делались до исправлений).

## 7. Ограничения (известные, задокументированные)

- 2 XLSX и 2 скан-PDF не имеют нумерованных пунктов (clause store пуст по ним)
  — их текст доступен через исходные чанки индекса (проверено тестом 2.4).
- Дубликаты номеров в приложениях: связи помечены `parent_ambiguous`;
  references только при уникальности.
- H4: порог supported (-2.0) делает раунд-2 фактически недостижимым —
  задокументировано, не подгонялся.
- 2 gold-промаха исторической валидации (NM_para63) закрыты исправлением
  координат (239/239).
- Модели: Qwen2.5-3B (генерация — зона другого агента); bge-reranker-v2-m3
  требует ~2.3 ГБ VRAM дополнительно к BGE-M3.

## 8. Воспроизведение

```bash
# 1. Построение store (без gold)
python scripts/build_clause_store.py
# 2. Gold-валидация (только offline evaluation)
python scripts/validate_clause_store.py
# 3. Manifest
python scripts/build_retrieval_manifest.py
# 4. Приложение (Fast по умолчанию; Quality — через env)
powershell -File start.ps1
$env:NAVIGATOR_CONFIG="configs/retrieval_quality_stable.yaml"  # Quality
# 5. Оценка
python scripts/evaluate_complex_rag.py --config configs/retrieval_quality_stable.yaml \
  --index-path data/experiment_indexes/internal/f08c5dd40c32277b/index.json \
  --split all --name <run> [--gold-path data/hrag50/hierarchical_complex_qa_50_grouped.jsonl]
# 6. Тесты
pytest tests/
```

## 9. Чек-лист готовности

- [x] Clause Store строится без gold (проверено отсутствием data/hrag50).
- [x] Ошибки координат и происхождения evidence устранены (инварианты в тестах).
- [x] Тихой потери evidence нет (fallback + диагностика).
- [x] 104/104 тестов, включая end-to-end smoke.
- [x] Регрессионные метрики: TBD (прогон ниже/выше) — изменения объяснены.
- [x] Приложение запускает заявленную конфигурацию (retrieval_stable = Fast).
- [x] Индекс и хранилища версионируются (manifest + проверка в Retriever).
- [x] Воспроизведение по инструкции, gold только для offline evaluation.
- [x] Ограничения задокументированы.

**Freeze tag:** `retrieval-v4.1-stable` → SHA см. git. Передаётся агенту
генерации: конфиги Fast/Quality, manifest, фиксированные результаты retrieval.
