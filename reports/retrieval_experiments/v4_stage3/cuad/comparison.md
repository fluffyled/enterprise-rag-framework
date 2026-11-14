# Experiment comparison

| Metric | v3_cuda_legal_bge_e2 | v4_cuad_bge_coverage | v4_cuad_bge_adaptive_v2 |
|---|---:|---:|---:|
| all_documents_hit@5 | 1.000000 | 1.000000 | 1.000000 |
| all_documents_hit@5_errors | 0 | 0 | 0 |
| all_evidence_hit@20 | 0.600000 | 0.500000 | 0.600000 |
| all_evidence_hit@6 | 0.165000 | 0.220000 | 0.285000 |
| all_evidence_hit@6_errors | 167 | 156 | 143 |
| covered_requirements | 0.315000 | 0.400000 | 0.520000 |
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
| evidence_precision | 0.022784 | 0.029472 | 0.037567 |
| evidence_recall@20 | 0.664071 | 0.576619 | 0.664071 |
| evidence_recall@6 | 0.212667 | 0.275500 | 0.356583 |
| gold_requirement_count | 1.620000 | 1.620000 | 1.620000 |
| gold_span_coverage | 0.154638 | 0.212687 | 0.261219 |
| gold_span_coverage@20 | 0.539451 | 0.472995 | 0.539451 |
| gold_span_coverage@6 | 0.154638 | 0.212687 | 0.261219 |
| mrr@10 | 0.111312 | 0.095468 | 0.111312 |
| mrr@5 | 1.000000 | 1.000000 | 1.000000 |
| ndcg@10 | 0.159654 | 0.124289 | 0.159654 |
| ndcg@5 | 1.000000 | 1.000000 | 1.000000 |
| questions | 200 | 200 | 200 |
| ranked_document_count | 2.405000 | 11.230000 | 2.405000 |
| redundancy_ratio | 0.000000 | 0.000000 | 0.000000 |
| requirements_total | 1.620000 | 1.620000 | 1.620000 |
| selected_characters | 4508.045000 | 4457.295000 | 4494.225000 |
| selected_tokens | 658.185000 | 658.305000 | 657.900000 |
| unique_documents | 1.390000 | 2.250000 | 1.495000 |
| median latency (s) | 0.574874 | 1.108314 | 0.435169 |
| index bytes | 35629778 | 35629778 | 35629778 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 200 |
| evidence_recall@6 | 0.14391666666666666 | [0.0899875, 0.19891666666666666] | 200 |
| all_evidence_hit@6 | 0.12 | [0.065, 0.18] | 200 |
| ndcg@10 | 0.0 | [0.0, 0.0] | 200 |
| gold_span_coverage | 0.10658181925662254 | [0.06463179175767735, 0.1553988350990317] | 200 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 0 | 0 | 200 |
| evidence_recall@6 | 42 | 5 | 153 |
| all_evidence_hit@6 | 29 | 5 | 166 |
| ndcg@10 | 0 | 0 | 200 |
| gold_span_coverage | 45 | 7 | 148 |
