# rag100 — таблица ошибок по вопросам (test, 74 отвечаемых)

| ID | Difficulty | B0_baseline | V2_stable | V2_mmr | V3F_final | BGE_e2 |
|---|---|---|---|---|---|---|
| Q001 | easy | ok | ok | ok | ok | ok |
| Q003 | medium | ok | ok | ok | ok | ok |
| Q004 | hard | ok | ok | ok | ok | ok |
| Q005 | medium | ok | ok | ok | ok | ok |
| Q006 | easy | ok | ok | ok | ok | ok |
| Q007 | medium | retrieval_miss (#None) | retrieval_miss (#None) | retrieval_miss (#None) | retrieval_miss (#None) | ok |
| Q008 | medium | ok | ok | ok | ok | ok |
| Q009 | medium | ok | ok | ok | ok | ok |
| Q010 | medium | ok | ok | ok | ok | ok |
| Q012 | medium | ok | ok | ok | ok | ok |
| Q013 | medium | ok | ok | ok | ok | ok |
| Q014 | medium | ok | ok | ok | ok | ok |
| Q015 | medium | ok | ok | ok | ok | ok |
| Q017 | easy | ok | ok | ok | ok | ok |
| Q018 | medium | ok | ok | ok | ok | ok |
| Q019 | medium | ok | ok | ok | ok | ok |
| Q021 | easy | ok | ok | ok | ok | ok |
| Q022 | medium | ok | ok | ok | ok | ok |
| Q023 | medium | ok | ok | ok | ok | ok |
| Q024 | medium | ok | ok | ok | ok | ok |
| Q025 | hard | ok | ok | ok | ok | ok |
| Q026 | hard | ok | ok | ok | ok | ok |
| Q028 | medium | ok | ok | ok | ok | ok |
| Q029 | hard | ok | ok | ok | ok | ok |
| Q030 | easy | ok | ok | ok | ok | ok |
| Q031 | hard | ok | ok | ok | ok | ok |
| Q032 | hard | ok | ok | ok | ok | ok |
| Q034 | medium | ok | ok | ok | ok | ok |
| Q035 | medium | ok | ok | ok | ok | ok |
| Q036 | hard | ok | ok | ok | ok | ok |
| Q037 | hard | ok | ok | ok | ok | ok |
| Q038 | medium | ok | ok | ok | ok | ok |
| Q039 | medium | ok | ok | ok | ok | ok |
| Q040 | hard | ok | ok | ok | ok | ok |
| Q041 | hard | ok | ok | ok | ok | ok |
| Q043 | medium | ok | ok | ok | ok | ok |
| Q045 | medium | ok | ok | ok | ok | ok |
| Q047 | hard | ok | ok | ok | ok | ok |
| Q049 | medium | ok | ok | ok | ok | ok |
| Q051 | hard | ok | ok | ok | ok | ok |
| Q052 | medium | ok | ok | ok | ok | ok |
| Q053 | medium | ok | ok | ok | ok | ok |
| Q054 | medium | ok | ok | ok | ok | ok |
| Q055 | medium | ok | ok | ok | ok | selection_error (#5) |
| Q056 | medium | ok | ok | ok | ok | ok |
| Q057 | easy | ok | ok | ok | ok | ok |
| Q058 | medium | unit_miss (#None) | unit_miss (#None) | unit_miss (#None) | unit_miss (#None) | unit_miss (#None) |
| Q059 | hard | ok | ok | ok | ok | ok |
| Q063 | medium | unit_miss (#None) | ok | unit_miss (#None) | ok | unit_miss (#None) |
| Q064 | medium | ok | ok | ok | ok | ok |
| Q065 | medium | ok | ok | ok | ok | ok |
| Q067 | hard | ok | ok | ok | ok | ok |
| Q070 | medium | ok | ok | ok | ok | ok |
| Q071 | medium | ok | ok | ok | ok | ok |
| Q072 | medium | ok | ok | ok | ok | ok |
| Q074 | medium | ok | ok | ok | ok | ok |
| Q075 | medium | ok | ok | ok | ok | ok |
| Q076 | medium | ok | ok | ok | ok | ok |
| Q077 | hard | unit_miss (#None) | unit_miss (#None) | unit_miss (#None) | unit_miss (#None) | ok |
| Q078 | medium | ok | ok | ok | ok | ok |
| Q079 | medium | unit_miss (#None) | unit_miss (#None) | unit_miss (#None) | unit_miss (#None) | unit_miss (#None) |
| Q080 | hard | ok | ok | ok | ok | ok |
| Q081 | medium | ok | ok | ok | ok | ok |
| Q082 | medium | ok | ok | ok | ok | ok |
| Q083 | medium | ok | ok | ok | ok | ok |
| Q084 | medium | ok | ok | ok | ok | ok |
| Q085 | medium | ok | ok | ok | ok | ok |
| Q086 | medium | ok | ok | ok | ok | ok |
| Q087 | medium | ok | ok | ok | ok | ok |
| Q088 | hard | ok | ok | ok | ok | ok |
| Q089 | hard | ok | ok | ok | ok | ok |
| Q090 | medium | ok | ok | ok | ok | ok |
| Q091 | medium | ok | ok | ok | ok | ok |
| Q092 | medium | ok | ok | ok | ok | ok |

## Сводка

| Конфиг | ok | retrieval_miss | unit_miss | ranking_error | selection_error |
|---|---|---|---|---|---|
| B0_baseline | 69 | 1 | 4 | 0 | 0 |
| V2_stable | 70 | 1 | 3 | 0 | 0 |
| V2_mmr | 69 | 1 | 4 | 0 | 0 |
| V3F_final | 70 | 1 | 3 | 0 | 0 |
| BGE_e2 | 70 | 0 | 3 | 0 | 1 |