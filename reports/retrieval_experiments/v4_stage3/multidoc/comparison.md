# Experiment comparison

| Metric | v3_cuda_multidoc_bge_e2 | v4_mdb_bge_protected | v4_mdb_bge_adaptive_v2 |
|---|---:|---:|---:|
| all_documents_hit@5 | 0.880000 | 0.880000 | 0.880000 |
| all_documents_hit@5_errors | 36 | 36 | 36 |
| all_evidence_hit@20 | 0.813333 | 0.813333 | 0.813333 |
| all_evidence_hit@6 | 0.656667 | 0.670000 | 0.660000 |
| all_evidence_hit@6_errors | 103 | 99 | 102 |
| covered_requirements | 0.656667 | 0.670000 | 0.660000 |
| document_hit@1 | 0.573333 | 0.573333 | 0.573333 |
| document_hit@10 | 0.950000 | 0.950000 | 0.950000 |
| document_hit@3 | 0.806667 | 0.806667 | 0.806667 |
| document_hit@5 | 0.880000 | 0.880000 | 0.880000 |
| document_mrr@10 | 0.703770 | 0.703770 | 0.703770 |
| document_ndcg@10 | 0.763871 | 0.763871 | 0.763871 |
| document_recall@1 | 0.573333 | 0.573333 | 0.573333 |
| document_recall@10 | 0.950000 | 0.950000 | 0.950000 |
| document_recall@3 | 0.806667 | 0.806667 | 0.806667 |
| document_recall@5 | 0.880000 | 0.880000 | 0.880000 |
| evidence_precision | 0.023813 | 0.024266 | 0.023929 |
| evidence_recall@20 | 0.813333 | 0.813333 | 0.813333 |
| evidence_recall@6 | 0.656667 | 0.670000 | 0.660000 |
| gold_requirement_count | 1.000000 | 1.000000 | 1.000000 |
| gold_span_coverage | 0.619917 | 0.634781 | 0.622073 |
| gold_span_coverage@20 | 0.785679 | 0.785679 | 0.785679 |
| gold_span_coverage@6 | 0.619917 | 0.634781 | 0.622073 |
| mrr@10 | 0.510000 | 0.510000 | 0.510000 |
| mrr@5 | 0.693833 | 0.693833 | 0.693833 |
| ndcg@10 | 0.532059 | 0.532059 | 0.532059 |
| ndcg@5 | 0.740636 | 0.740636 | 0.740636 |
| questions | 300 | 300 | 300 |
| ranked_document_count | 9.026667 | 9.026667 | 9.026667 |
| redundancy_ratio | 0.012046 | 0.009289 | 0.012046 |
| requirements_total | 1.000000 | 1.000000 | 1.000000 |
| selected_characters | 3664.216667 | 3659.930000 | 3661.673333 |
| selected_tokens | 651.016667 | 650.310000 | 650.576667 |
| unique_documents | 3.623333 | 3.706667 | 3.643333 |
| median latency (s) | 1.518917 | 0.743646 | 0.743863 |
| index bytes | 113782028 | 113782028 | 113782028 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 300 |
| evidence_recall@6 | 0.0033333333333333335 | [0.0, 0.01] | 300 |
| all_evidence_hit@6 | 0.0033333333333333335 | [0.0, 0.01] | 300 |
| ndcg@10 | 0.0 | [0.0, 0.0] | 300 |
| gold_span_coverage | 0.0021557971014492753 | [0.0, 0.006467391304347826] | 300 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 0 | 0 | 300 |
| evidence_recall@6 | 1 | 0 | 299 |
| all_evidence_hit@6 | 1 | 0 | 299 |
| ndcg@10 | 0 | 0 | 300 |
| gold_span_coverage | 1 | 0 | 299 |
