# Источники интеграции

| Компонент | Ветка | SHA | Основные файлы | Пересечения |
|---|---|---|---|---|
| Retrieval | sevsese | c9e36f2db91237d86e7e2b239c02119e541d7152 | navigator/retrieval.py, navigator/parent_expansion.py, configs/ | Экспериментальные настройки G2 исключены |
| Generation | experiment/generation-v2 | 855b181b3772e2dda19e066a28270814ab85e3e4 | answering/v2/, answering/core.py, answer-model.lock.json | navigator/answer.py остаётся baseline |
| UI | developer-2/answer-generation | 34e171f7db173dcee42d009dccea9a4eaa188171 | app.py, ui/, demo_fixtures/, tests/test_ui.py | Backend адаптирован к Application Service |
| Evaluation | sevsese и experiment/generation-v2 | 236de3a534db83d87472a70c683deb71422c2372 и 855b181b3772e2dda19e066a28270814ab85e3e4 | navigator/evaluation/, scripts/evaluate_*.py | Oracle используется только при оценке |

HEAD sevsese включает исправления Retrieval Audit и стабилизацию abab6d16ec2155fbdb7a44d94049be434c13e10a. История UI показывает переход на оболочку ui/ в 34e171f. Отдельный frontend/web для неё отсутствует. Из ветки UI перенесены оболочка, staging, представления и тесты. Из ветки G2 перенесены модуль, тесты и исследовательские сценарии.
