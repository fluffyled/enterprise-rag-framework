# Experiment comparison

| Metric | v3_cuda_legal_bge_e2 | v4_cuad_bge_coverage | v4_cuad_bge_protected |
|---|---:|---:|---:|
| all_documents_hit@5 | 1.000000 | 1.000000 | 1.000000 |
| all_documents_hit@5_errors | 0 | 0 | 0 |
| all_evidence_hit@20 | 0.600000 | 0.500000 | 0.600000 |
| all_evidence_hit@6 | 0.165000 | 0.220000 | 0.175000 |
| all_evidence_hit@6_errors | 167 | 156 | 165 |
| covered_requirements | 0.315000 | 0.400000 | 0.330000 |
| document_hit@1 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@10 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@3 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@5 | 1.000000 | 1.000000 | 1.000000 |
| document_mrr@10 | 1.000000 | 1.000000 | 1.000000 |
| document_ndcg@10 | 1.000000 | 1.000000 | 1.000000 |
| document_recall@1 | 1.000000 | 1.000000 | 1.000000 |
| document_recall@10 | 1.000000 | 1.000000 | 1.000000 |
| document_recall@3 | 1.000000 | 1.000000 | 1.000000 |
| document_recall@5 | 1.000000 | 1.000000 | 1.000000 |
| evidence_precision | 0.022784 | 0.029472 | 0.024300 |
| evidence_recall@20 | 0.664071 | 0.576619 | 0.664071 |
| evidence_recall@6 | 0.212667 | 0.275500 | 0.223929 |
| gold_requirement_count | 1.620000 | 1.620000 | 1.620000 |
| gold_span_coverage | 0.154638 | 0.212687 | 0.156770 |
| gold_span_coverage@20 | 0.539451 | 0.472995 | 0.539451 |
| gold_span_coverage@6 | 0.154638 | 0.212687 | 0.156770 |
| mrr@10 | 0.111312 | 0.095468 | 0.111312 |
| mrr@5 | 1.000000 | 1.000000 | 1.000000 |
| ndcg@10 | 0.159654 | 0.124289 | 0.159654 |
| ndcg@5 | 1.000000 | 1.000000 | 1.000000 |
| questions | 200 | 200 | 200 |
| ranked_document_count | 2.405000 | 11.230000 | 2.405000 |
| redundancy_ratio | 0.000000 | 0.000000 | 0.000000 |
| requirements_total | 1.620000 | 1.620000 | 1.620000 |
| selected_characters | 4508.045000 | 4457.295000 | 4514.980000 |
| selected_tokens | 658.185000 | 658.305000 | 658.185000 |
| unique_documents | 1.390000 | 2.250000 | 1.405000 |
| median latency (s) | 0.574874 | 1.108314 | 0.341859 |
| index bytes | 35629778 | 35629778 | 35629778 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 200 |
| evidence_recall@6 | 0.011261904761904761 | [-0.008575595238095238, 0.032622619047619025] | 200 |
| all_evidence_hit@6 | 0.01 | [-0.01, 0.03] | 200 |
| ndcg@10 | 0.0 | [0.0, 0.0] | 200 |
| gold_span_coverage | 0.0021324260652343155 | [-0.01458143070207461, 0.01875424391915397] | 200 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 0 | 0 | 200 |
| evidence_recall@6 | 5 | 3 | 192 |
| all_evidence_hit@6 | 3 | 1 | 196 |
| ndcg@10 | 0 | 0 | 200 |
| gold_span_coverage | 5 | 4 | 191 |
