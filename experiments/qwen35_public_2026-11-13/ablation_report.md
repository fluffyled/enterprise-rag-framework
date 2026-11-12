# Абляции

A0/A1 — контролируемая смена единицы выбора. A2 против A0 смешивает блоки, staging и свободное формирование ответа; приписывать разницу только evidence-first нельзя.

Дополнительные dev-контроли: 3 good вопроса с релевантными документами в начале/середине/конце; те же 3 с коротким oracle-контекстом только gold-documents; one-step generation на 3 good + 3 OOD. Всего 18 запусков, один seed, случайно перемешанный порядок условий. One-step использует тот же generation prompt/schema/decoding, но получает все блоки без предварительного выбора. Это маленький диагностический срез; семантическая оценка не валидирована и выбор production-конфигурации на этих данных не делается.

| Условие | case_id | Статус | Секунды | Вызовы |
|---|---|---|---|---|
| one_step_full | AX83rLL97qA9ExzJ64W9Nd | answered | 3.67 | 1 |
| one_step_full | B5XoMtCDcqgj4NpjhCvLf8 | insufficient | 1.903 | 1 |
| one_step_full | BArtXWHjBDRkGUtzKS7TUA | answered | 7.29 | 1 |
| one_step_full | dYEgw9hGC8oxZVgdLCUFRd | insufficient | 4.382 | 1 |
| one_step_full | KUs3SzTJnh5iAAx7hgMyBq | insufficient | 4.012 | 1 |
| one_step_full | VkAfu7onUZHS25zvNLCw6H | insufficient | 9.389 | 1 |
| relevant_first | AX83rLL97qA9ExzJ64W9Nd | answered | 4.452 | 2 |
| relevant_first | BArtXWHjBDRkGUtzKS7TUA | answered | 8.018 | 2 |
| relevant_first | KUs3SzTJnh5iAAx7hgMyBq | insufficient | 1.903 | 1 |
| relevant_last | AX83rLL97qA9ExzJ64W9Nd | answered | 4.523 | 2 |
| relevant_last | BArtXWHjBDRkGUtzKS7TUA | answered | 8.739 | 2 |
| relevant_last | KUs3SzTJnh5iAAx7hgMyBq | insufficient | 1.911 | 1 |
| relevant_middle | AX83rLL97qA9ExzJ64W9Nd | answered | 4.451 | 2 |
| relevant_middle | BArtXWHjBDRkGUtzKS7TUA | answered | 9.619 | 2 |
| relevant_middle | KUs3SzTJnh5iAAx7hgMyBq | insufficient | 1.917 | 1 |
| short_oracle_gold_docs | AX83rLL97qA9ExzJ64W9Nd | answered | 3.166 | 2 |
| short_oracle_gold_docs | BArtXWHjBDRkGUtzKS7TUA | answered | 7.474 | 2 |
| short_oracle_gold_docs | KUs3SzTJnh5iAAx7hgMyBq | insufficient | 1.914 | 1 |

Thinking и temperature не перебирались: приоритет был у основных механизмов и исправления протокола. Не проводился отдельный валидированный эксперимент локального entailment-checker; self-judge выявил собственные ошибки. Все гипотезы перечислены, непроверенные не объявлены улучшениями.
