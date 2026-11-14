# Experiment comparison

| Metric | v3_cuda_multidoc_bge_e2 | v4_mdb_bge_coverage | v4_mdb_bge_protected |
|---|---:|---:|---:|
| all_documents_hit@5 | 0.880000 | 0.880000 | 0.880000 |
| all_documents_hit@5_errors | 36 | 36 | 36 |
| all_evidence_hit@20 | 0.813333 | 0.813333 | 0.813333 |
| all_evidence_hit@6 | 0.656667 | 0.656667 | 0.670000 |
| all_evidence_hit@6_errors | 103 | 103 | 99 |
| covered_requirements | 0.656667 | 0.656667 | 0.670000 |
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
| evidence_precision | 0.023813 | 0.023822 | 0.024266 |
| evidence_recall@20 | 0.813333 | 0.813333 | 0.813333 |
| evidence_recall@6 | 0.656667 | 0.656667 | 0.670000 |
| gold_requirement_count | 1.000000 | 1.000000 | 1.000000 |
| gold_span_coverage | 0.619917 | 0.619917 | 0.634781 |
| gold_span_coverage@20 | 0.785679 | 0.785679 | 0.785679 |
| gold_span_coverage@6 | 0.619917 | 0.619917 | 0.634781 |
| mrr@10 | 0.510000 | 0.510000 | 0.510000 |
| mrr@5 | 0.693833 | 0.693833 | 0.693833 |
| ndcg@10 | 0.532059 | 0.532059 | 0.532059 |
| ndcg@5 | 0.740636 | 0.740636 | 0.740636 |
| questions | 300 | 300 | 300 |
| ranked_document_count | 9.026667 | 9.093333 | 9.026667 |
| redundancy_ratio | 0.012046 | 0.012046 | 0.009289 |
| requirements_total | 1.000000 | 1.000000 | 1.000000 |
| selected_characters | 3664.216667 | 3662.670000 | 3659.930000 |
| selected_tokens | 651.016667 | 650.756667 | 650.310000 |
| unique_documents | 3.623333 | 3.626667 | 3.706667 |
| median latency (s) | 1.518917 | 0.751235 | 0.743646 |
| index bytes | 113782028 | 113782028 | 113782028 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 300 |
| evidence_recall@6 | 0.013333333333333334 | [-0.0033333333333333335, 0.03333333333333333] | 300 |
| all_evidence_hit@6 | 0.013333333333333334 | [-0.0033333333333333335, 0.03333333333333333] | 300 |
| ndcg@10 | 0.0 | [0.0, 0.0] | 300 |
| gold_span_coverage | 0.014864130434782607 | [-0.000625, 0.03251403985507244] | 300 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 0 | 0 | 300 |
| evidence_recall@6 | 6 | 2 | 292 |
| all_evidence_hit@6 | 6 | 2 | 292 |
| ndcg@10 | 0 | 0 | 300 |
| gold_span_coverage | 6 | 2 | 292 |
