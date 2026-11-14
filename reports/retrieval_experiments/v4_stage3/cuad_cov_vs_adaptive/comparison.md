# Experiment comparison

| Metric | v4_cuad_bge_coverage | v4_cuad_bge_adaptive_v2 |
|---|---:|---:|
| all_documents_hit@5 | 1.000000 | 1.000000 |
| all_documents_hit@5_errors | 0 | 0 |
| all_evidence_hit@20 | 0.500000 | 0.600000 |
| all_evidence_hit@6 | 0.220000 | 0.285000 |
| all_evidence_hit@6_errors | 156 | 143 |
| covered_requirements | 0.400000 | 0.520000 |
| document_hit@1 | 1.000000 | 1.000000 |
| document_hit@10 | 1.000000 | 1.000000 |
| document_hit@3 | 1.000000 | 1.000000 |
| document_hit@5 | 1.000000 | 1.000000 |
| document_mrr@10 | 1.000000 | 1.000000 |
| document_ndcg@10 | 1.000000 | 1.000000 |
| document_recall@1 | 1.000000 | 1.000000 |
| document_recall@10 | 1.000000 | 1.000000 |
| document_recall@3 | 1.000000 | 1.000000 |
| document_recall@5 | 1.000000 | 1.000000 |
| evidence_precision | 0.029472 | 0.037567 |
| evidence_recall@20 | 0.576619 | 0.664071 |
| evidence_recall@6 | 0.275500 | 0.356583 |
| gold_requirement_count | 1.620000 | 1.620000 |
| gold_span_coverage | 0.212687 | 0.261219 |
| gold_span_coverage@20 | 0.472995 | 0.539451 |
| gold_span_coverage@6 | 0.212687 | 0.261219 |
| mrr@10 | 0.095468 | 0.111312 |
| mrr@5 | 1.000000 | 1.000000 |
| ndcg@10 | 0.124289 | 0.159654 |
| ndcg@5 | 1.000000 | 1.000000 |
| questions | 200 | 200 |
| ranked_document_count | 11.230000 | 2.405000 |
| redundancy_ratio | 0.000000 | 0.000000 |
| requirements_total | 1.620000 | 1.620000 |
| selected_characters | 4457.295000 | 4494.225000 |
| selected_tokens | 658.305000 | 657.900000 |
| unique_documents | 2.250000 | 1.495000 |
| median latency (s) | 1.108314 | 0.435169 |
| index bytes | 35629778 | 35629778 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 200 |
| evidence_recall@6 | 0.08108333333333333 | [0.038914583333333336, 0.1265] | 200 |
| all_evidence_hit@6 | 0.065 | [0.02, 0.11012499999999932] | 200 |
| ndcg@10 | 0.0353644993614416 | [0.022611600641662767, 0.0490897828560006] | 200 |
| gold_span_coverage | 0.04853243305415851 | [0.014949703819912459, 0.08683463141785817] | 200 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 0 | 0 | 200 |
| evidence_recall@6 | 26 | 6 | 168 |
| all_evidence_hit@6 | 17 | 4 | 179 |
| ndcg@10 | 56 | 7 | 137 |
| gold_span_coverage | 29 | 8 | 163 |
