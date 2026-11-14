# Experiment comparison

| Metric | v3_cuda_legal_bge_e2 | v4_cuad_bge_adaptive_v2 | v4_cuad_bge_rerank |
|---|---:|---:|---:|
| all_documents_hit@5 | 1.000000 | 1.000000 | 1.000000 |
| all_documents_hit@5_errors | 0 | 0 | 0 |
| all_evidence_hit@20 | 0.600000 | 0.600000 | 0.600000 |
| all_evidence_hit@6 | 0.165000 | 0.285000 | 0.380000 |
| all_evidence_hit@6_errors | 167 | 143 | 124 |
| covered_requirements | 0.315000 | 0.520000 | 0.730000 |
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
| evidence_precision | 0.022784 | 0.037567 | 0.059099 |
| evidence_recall@20 | 0.664071 | 0.664071 | 0.664071 |
| evidence_recall@6 | 0.212667 | 0.356583 | 0.451012 |
| gold_requirement_count | 1.620000 | 1.620000 | 1.620000 |
| gold_span_coverage | 0.154638 | 0.261219 | 0.347108 |
| gold_span_coverage@20 | 0.539451 | 0.539451 | 0.539451 |
| gold_span_coverage@6 | 0.154638 | 0.261219 | 0.347108 |
| mrr@10 | 0.111312 | 0.111312 | 0.272552 |
| mrr@5 | 1.000000 | 1.000000 | 1.000000 |
| ndcg@10 | 0.159654 | 0.159654 | 0.320018 |
| ndcg@5 | 1.000000 | 1.000000 | 1.000000 |
| questions | 200 | 200 | 200 |
| ranked_document_count | 2.405000 | 2.405000 | 2.405000 |
| redundancy_ratio | 0.000000 | 0.000000 | 0.000000 |
| requirements_total | 1.620000 | 1.620000 | 1.620000 |
| selected_characters | 4508.045000 | 4494.225000 | 4504.615000 |
| selected_tokens | 658.185000 | 657.900000 | 658.785000 |
| unique_documents | 1.390000 | 1.495000 | 1.475000 |
| median latency (s) | 0.574874 | 0.435169 | 0.811703 |
| index bytes | 35629778 | 35629778 | 35629778 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 200 |
| evidence_recall@6 | 0.23834523809523808 | [0.17482886904761907, 0.2988589285714286] | 200 |
| all_evidence_hit@6 | 0.215 | [0.15, 0.275] | 200 |
| ndcg@10 | 0.16036408042381428 | [0.1268923563641383, 0.1953667893154165] | 200 |
| gold_span_coverage | 0.19247064609562034 | [0.13957973126069967, 0.2433199428411285] | 200 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 0 | 0 | 200 |
| evidence_recall@6 | 65 | 9 | 126 |
| all_evidence_hit@6 | 47 | 4 | 149 |
| ndcg@10 | 104 | 22 | 74 |
| gold_span_coverage | 71 | 11 | 118 |
