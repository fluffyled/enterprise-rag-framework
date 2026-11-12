from pathlib import Path
import json,csv,statistics,hashlib
from metrics import ARMS,read,aggregate,rows
ROOT=Path(__file__).parent

def fmt(v,key=''):
 if v is None:return 'N/A'
 if isinstance(v,int):return str(v)
 return f'{v:.2f}' if any(x in key for x in ['seconds','MiB','calls','tokens','characters']) else f'{v*100:.1f}%'

def wide(data,keys):
 lines=['| Метрика | A0 | A1 | A2 | A3† | A4 |','|---|---:|---:|---:|---:|---:|']
 for label,key in keys:lines.append('| '+label+' | '+' | '.join(fmt(data[a].get(key),key) for a in ARMS)+' |')
 return '\n'.join(lines)

def main():
 summary=read(ROOT/'metrics_comparison.json');mapping={ds:{r['arm']:r for r in summary if r['dataset']==ds} for ds in {r['dataset'] for r in summary}};ru=mapping['grounded_ru'];md=mapping['multidoc2dial'];boot=list(csv.DictReader((ROOT/'paired_bootstrap.csv').open(encoding='utf-8-sig')))
 exact=[('Отказ на good — относительно метки','False Refusal Rate [exact]'),('Ответ на OOD — относительно метки','False Answer Rate OOD [exact]'),('Abstention Precision','Abstention Precision [exact]'),('Abstention Recall','Abstention Recall [exact]'),('Abstention F1','Abstention F1 [exact]'),('Gold document ID Precision (не semantic citation)','Gold document ID Precision [exact]'),('Gold document ID Recall (не полнота фактов)','Gold document ID Recall [exact]'),('JSON Validity по схеме наблюдаемых ответов','JSON Validity [schema, observed responses]'),('Валидность итогового программного контракта','Contract Validity [exact]'),('Error Rate','Error Rate [exact]'),('Доля partial','Partial Answer Rate [exact]'),('Median Latency, seconds','Median Latency seconds'),('p95 Latency, seconds','p95 Latency seconds'),('Медиана только answered/partial, seconds','Median answered latency seconds'),('Peak VRAM, MiB — всё устройство, sampled','Peak VRAM MiB [device-wide sampled]'),('Peak server working set, MiB — sampled','Peak server working set MiB [sampled]'),('Среднее число model calls','Mean model calls'),('Средние prompt tokens','Mean prompt tokens'),('Средние output tokens','Mean output tokens'),('Средние символы итогового текста','Mean output characters')]
 ci=['| Сравнение | Метрика | Разница | 95% CI |','|---|---|---:|---:|']
 for b in boot:
  if b['dataset']=='grounded_ru' and b['metric']in ['False Refusal Rate [exact]','Gold document ID Recall [exact]','False Answer Rate OOD [exact]'] and b['difference']:
   ci.append(f"| {b['comparison']} | {b['metric']} | {float(b['difference'])*100:+.1f} п.п. | [{float(b['ci95_low'])*100:+.1f}; {float(b['ci95_high'])*100:+.1f}] |")
 audit=read(ROOT/'source_review_metrics.json');manual=wide(audit['metrics'],[(x,x) for x in audit['metric_order']]);coverage=read(ROOT/'semantic_coverage.json');rscount=len(list((ROOT/'runs').rglob('*.json')));conf=[]
 for aid in ['A0_baseline','A3_procedure_v3']:
  rr=[read(f) for f in (ROOT/'runs/confirmation'/aid).glob('*.json')];conf.append(f"{aid}: "+', '.join(f'{status}={sum(r["status"]==status for r in rr)}' for status in ['answered','partial','insufficient','error']))
 text=f'''# Эксперимент Qwen3.5-4B для RAG МФТИ

**Результат: универсальное улучшение исходного генератора не доказано.** У целых блоков есть проверенные локальные выигрыши полноты и сохранения условий. Строгий Evidence-first уменьшает OOD-ответы относительно разметки, но повышает отказы на good. Partial восстанавливает часть выдачи и увеличивает набор gold ID, однако найдено перепутывание сущностей и неподтверждённое требование документа. Поэтому A2/A3/A4 не устанавливаются обязательной заменой исходного генератора.

Это реальный локальный эксперимент, а не предложение эксперимента: в runs сохранено **{rscount} отдельных case/configuration результатов**, плюс dev-абляции и диагностические повторы. Основная таблица содержит 200 ответов пяти финальных конфигураций на 40 одинаковых test-примерах; исходный совместный A3-v2 сохранён отдельно ещё на 40 test-примерах. Структурная версия A3 исправлена после исходного test и явно помечена †. Полный журнал позволяет восстановить все сравнения.

## 1. Датасеты

[Grounded-RAG-RU-v2](https://huggingface.co/datasets/Vikhrmodels/Grounded-RAG-RU-v2): официальный train 50 010 / test 200; скачаны первый train shard 25 005 и официальный test 200. Использованы 24 dev и 32 test (поровну good/OOD). Это короткоконтекстный срез до 2600 input tokens, а не полный benchmark. В test 15 связанных документных групп, 9 многодокументных gold-вопросов; 13 отвечаемых примеров содержат отвлекающие документы. Reference и relevant_doc_ids разобраны из разных реплик assistant и не передавались генератору.

[MultiDoc2Dial](https://doc2dial.github.io/multidoc2dial/): 4 train-примера для dev, 8 validation-примеров для отдельного test-среза. Контекст — oracle-секции вокруг gold spans, без запуска Retrieval; языки документов/эталонов английские, новые ответы русские. Все 8 формально answerable, но два примера имеют известные дефекты. Дополнительная clean sensitivity из 6 показана в CSV. Это не официальный полный результат MultiDoc2Dial.

Документные компоненты dev/test не пересекаются по cluster, точному нормализованному тексту и непустым заголовкам. Seed 20261113. Исходные чанки, эталоны и лицензии не гарантируют безошибочность: найден ошибочный good-вопрос про разные фамилии и неверные gold-ID для вопроса на букву «А». Исходные метки не исправлялись скрытно. Поэтому «False Refusal» здесь точно рассчитан **относительно официальной метки**, но не является доказанной истинной частотой необоснованного отказа.

Карточка Grounded-RAG-RU-v2 декларирует Apache-2.0; происхождение текстов Википедии учитывается отдельно. У MD metadata Apache-2.0 расходится с разделом Licensing Information CC BY 3.0. Источники, revisions, SHA256, декларации и расхождения сохранены в [manifest](dataset_manifest.json). Частные 60 вопросов напарника не использованы и не изображены доступными данными.

## 2. Зафиксированная исходная модель

Существующий файл `D:\\хакатон\\models\\answer-llm\\Qwen3.5-4B-Q4_K_M.gguf` повторно не скачивался. SHA256: `00fe7986ff5f6b463e62455821146049db6f9313603938a70800d1fb69ef11a4`.

llama.cpp b12284 / 9e9619d03, CUDA 12.4, RTX 3050 Laptop 4 ГБ, RAM около 15.6 GiB. Фактически offloaded 33/33 layers; лог также показывает CPU-mapped model buffer 497.31 MiB и CUDA model buffer 2603.50 MiB. Это GPU-инференс, а не обещание отсутствия любого CPU-оператора. Context 4096, flash attention on, KV K/V q8_0, batch 128 / ubatch 64, threads 4 / parallel 1. Temperature 0, seed 20261113, enable_thinking=false, cache_prompt=false. A0/A1 max output 300; evidence 300; ответ A2/A4 600; extraction A3 700 и его итоговый ответ 600. Chat template и system prompts сохранены в frozen и configuration_manifest.json.

A0 воспроизводит исходный выбор предложений и программную проверку цитат из snapshot напарника. Проблемы: обрыв на сокращениях («род.»), выбор сопутствующего текста, пропущенные соседние требования. Один dev-ответ нарушил контракт конфликтов: один и тот же документ по обе стороны. JSON-валидность и валидация смыслового контракта разделены. Оригинальный HTTP-пакет этого dev-сбоя не сохранился; отдельный replay отмечен как повтор, а не подмена оригинала.

## 3. Изменения

- A1: только смена предложений на целые доступные абзацы/пункты; тот же исходный prompt, schema и decoding. Нет выдуманных пунктов. Выбор ID затем возвращает буквальные блоки, поэтому длинный текст выдаётся без свободного пересказа.
- A2 v2: выбор evidence, затем краткое формирование ответа с цитатами. Проверяются существование ID и схема; семантическая поддержка отдельно. v0 и v2 не смешаны: v0 давал массовые ложные отказы, после dev исправлен слишком широкий запрет действий/сроков.
- A3† procedure v3: evidence selection → отдельное извлечение action/actor/condition/deadline/evidence_ids → отдельный итоговый ответ. Это реальная предварительная экстракция по протоколу, однако модель выдала is_procedure=false во всех 28 dev и 40 test случаях; ветка actions не активировалась. Процедурные вопросы про COE и риск потери жилья отсеялись ещё на evidence selection. Поэтому полезность структурированного извлечения не доказана, а дополнительный вызов сам по себе ничего не исправил. Ранний A3-v2 формировал claims/actions совместно; он сохранён как отдельный прототип и не выдан за строгую последовательность.
- A4 v2: Evidence-first с partial на обеих стадиях; только полезная доказанная часть должна сообщаться как неполная. Найдены ошибки калибровки: полный однозначный ответ иногда помечается partial; сопутствующий факт иногда выдаётся вместо нужного ответа.

A0/A1/A2/A4 и ранний joint-A3 были зафиксированы pretest_lock.json до первого test-вызова. A3-v3 — раскрытое исправление протокола по сравнению кода с исходным заданием, после появления первоначальных ответов; его основной test **не считается новым независимым слепым подтверждением**. Prompt не подбирался по его test-баллам. Для отдельной свежей проверки отложены 5 ещё не использованных official-test групп (1 good / 4 OOD), не пересекающихся документами с dev/main test. Четыре OOD здесь имеют пустой контекст и завершаются программным guard без вызова модели; содержательно это только один дополнительный good-вопрос. Этот срез не подтверждает качество отказов LLM и слишком мал для значимости. Результаты: {'; '.join(conf)}.

## 4. Основные результаты: RU, 32 вопроса

{wide(ru,exact)}

Для A0 ответы на OOD: 3/16; good-отказы: 2/16. Для A2: 1/16 и 9/16 соответственно. У A4: 3/16 и 2/16. Рост gold-ID recall у A4 не является ростом Faithfulness: в примере с хуторами обе ссылки присутствуют, а числа привязаны к неправильным названиям.

![Качество и задержка](quality_latency.png)

2000 парных bootstrap повторов по 15 документным компонентам, seed 20261113; разница arm − A0. Датасеты не смешаны. Интервалы описывают этот срез, не МФТИ в целом; † остаётся ограничением A3.

{chr(10).join(ci)}

Интервалы для всех предусмотренных сравнений, включая диагностические self-judge оценки, находятся в paired_bootstrap.csv. Если CI включает ноль, уверенный выигрыш не заявляется. Для семантических чисел отсутствие нуля всё равно не устраняет ошибку самого судьи.

## 5. Процедуры и проверка смысла

Независимой человеческой разметки Faithfulness/Correctness нет. Повторные вызовы той же Qwen сохранены, но выборочная проверка показала смешение неполноты с неподтверждённостью и ложный critical flag. Поэтому self-judge **не принят как валидированный арбитр**. Его результаты — диагностическое приложение в metrics_comparison.csv, с явными названиями и общим оцениваемым набором. Общих независимых значений семантических метрик нет: N/A. У судьи есть пропуски из-за context limit и ошибки; common comparable cases = {len(coverage['common_case_ids'])} из 40, список и покрытия — semantic_coverage.json.

Ниже дополнительный **ручной разбор агентом по исходным текстам**, без независимой человеческой проверки, выбранный после ответов для анализа ошибок. Это наблюдения на явно указанных малых срезах, не переносимые средние benchmark-качества. Faithfulness/UCR/Correctness/semantic citations/UAR — только 2 MD-кейса: отзыв заявления и COE. CPR — 6 проверенных условий в 4 MD-кейсах; Procedure Completeness — 7 единиц ответа в 4 MD-кейсах. Полные атомы, решения и объяснения — source_review.json. Нулевые знаменатели отдельно дают N/A. Промежуточные traces не считаются итоговым текстом.

{manual}

Все исходные 8 MD test-примеров по точным метрикам:

{wide(md,exact)}

Условие первоначального SSN и ограничение помощи участием в co-op важнее формального наличия ID. «Подать заявку на COE» нельзя заменять требованием уже получить документ для доступа к помощи. Локальный выигрыш A1 — сохранение возврата выплат рядом с 12-месячным сроком и сохранение ограничений co-op. Одновременно A1 раздувает краткие фактические ответы до целой биографии и повышает отказы на RU good относительно метки.

## 6. Анализ ошибок

[error_analysis.md](error_analysis.md) содержит реальные ответы до/после: сохранённый шаг, потерянное условие, перепутанные сущности и источники, неизменившийся правильный факт, ложный partial, ошибочный эталон и неподтверждённое требование. Категории без надёжной разметки или наблюдений так и обозначены; ошибки порядка действий и истинный глобальный UAR не выдуманы.

Обнаружена ошибка нашей подготовки MD oracle-контекста: text_sec был взят без доступного title «Do not». Исправление находится в structured_context.py; отдельный незаслеплённый контекстный case study не подмешан в основной benchmark. Это показывает, почему генератор не должен компенсировать потерянное отрицание своими знаниями. Исходные фиксированные входы и ответы не переписаны.

## 7. Скорость, память и абляции

Число вызовов и полный wall-clock показаны выше. Отказы часто завершаются на первой стадии: поэтому общая медиана A2/A3 может выглядеть близкой к A0, хотя отвечаемые запросы требуют двух/трёх вызовов. Отдельная медиана answered/partial предотвращает такую подмену. GPU-память — sampled device-wide значение, не точный эксклюзивный пик процесса. Main test серийный; фиксированный порядок arm и нагрев GPU ограничивают сравнение без повторов. Некоторые dev-v0/v2 вызовы пересекались в очереди и для speed claim не используются.

[ablation_report.md](ablation_report.md): 18 дополнительных dev-вызовов проверяют начало/середину/конец, полный/короткий oracle-контекст и one-step против evidence-first. Малый срез не доказывает общий эффект. Thinking и перебор температуры не выполнялись; проверенные и непроверенные гипотезы разделены. Денежных API-вызовов генерации нет: все нейросетевые запросы локальные. Электроэнергия и износ не измерялись, нулевая полная стоимость не заявляется.

## 8. Научное обоснование

[research_basis.md](research_basis.md) связывает протокол с [ALCE](https://arxiv.org/abs/2305.14627), [Sufficient Context](https://arxiv.org/abs/2411.06037), [MultiDoc2Dial](https://arxiv.org/abs/2109.12595), [Lost in the Middle](https://arxiv.org/abs/2307.03172) и исследованием [document-grounded evaluation](https://arxiv.org/abs/2309.11838). Они обосновывают проверку атрибуции, достаточности контекста, позиции доказательств и ограничений автоматического оценивания; не доказывают выигрыш данного квантованного checkpoint.

## 9. Применимость к МФТИ и рекомендация

Проверены механизмы на открытых данных, а не качество внутреннего навигатора. В Википедии меньше обязательных согласований, редакций и локальных ролей; MD англоязычный и oracle. Отсутствуют реальная выдача и scores Retrieval напарника, частный holdout и независимая проверка регламентов. End-to-end вывод о МФТИ делать нельзя.

**Сохранить A0 контролем; A1 считать кандидатом для проверки процедурных регламентов, а не универсальной обязательной заменой.** Преимущество целых блоков подтверждено отдельными примерами, но краткость и отказы регрессируют. A2 слишком часто отказывается относительно меток; A3 добавляет вызов и не устраняет доказанные ограничения автоматически; A4 нельзя принимать по снижению отказов/росту ID recall из-за обнаруженных семантических ошибок. Production-код и Retrieval не переключены.

Для интеграционной проверки передавать устойчивые document/block IDs и исходные заголовки/условия, отображать partial явно и проверять не только наличие ID, но и связь каждого утверждения с доказательством. На новых закрытых документах МФТИ нужны независимые метки обязательных шагов/условий и критических ошибок. Веса 40/25/20/15 не считаются официальными и не используются как единственный критерий: высокий средний балл может скрыть один выдуманный обязательный срок или документ.

## 10. Следующий этап и воспроизводимость

[training_feasibility.md](training_feasibility.md): обучение не запускалось. LoRA может сохранять базу замороженной, но имеющегося GGUF недостаточно для стандартного SFT. Документация Unsloth указывает около 10 ГБ для BF16 LoRA 4B и предупреждает о QLoRA для Qwen3.5. На этой 4-ГБ GPU сначала улучшать контекст, метки и генератор. Переход к обучению оправдан лишь для устойчивых, независимо подтверждённых ошибок при достаточном контексте и наличии проверенного train/нового holdout.

Все рабочие файлы находятся в `D:\\хакатон\\experiments\\qwen35_public_2026-11-13`. Ветки main/sevsese, исходные индексы и веса не менялись. Повторные запуски сохранять в новой директории; существующие per-case результаты не перезаписывать. baseline.py и run_v2.py пропускают имеющиеся записи и создают новые через exclusive open. Конфигурации и raw HTTP запросы/ответы сохранены, version hashes — в manifest/lock и итоговом integrity manifest.

Основные файлы: dataset_manifest.json, model_manifest.json, configuration_manifest.json, baseline_results.json, a1_results.json, a2_results.json, a3_results.json, a4_results.json, metrics_comparison.csv, per_case_metrics.csv, paired_bootstrap.csv, source_review.json, source_review_metrics.json, error_analysis.md, ablation_report.md, training_feasibility.md. Исходный joint-A3-v2 не удалён. Успешные HTTP-вызовы содержат usage/latency и точную schema; известная потеря original raw одного A0 dev-сбоя раскрыта выше.
'''
 (ROOT/'final_experiment_report.md').write_text(text,encoding='utf8');print('Final technical report saved')
if __name__=='__main__':main()
