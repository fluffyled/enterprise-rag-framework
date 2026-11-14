# Experiment comparison

| Metric | v3_cuda_multidoc_bge_e2 | v4_mdb_bge_adaptive_v2 | v4_mdb_bge_rerank |
|---|---:|---:|---:|
| all_documents_hit@5 | 0.880000 | 0.880000 | 0.933333 |
| all_documents_hit@5_errors | 36 | 36 | 20 |
| all_evidence_hit@20 | 0.813333 | 0.813333 | 0.813333 |
| all_evidence_hit@6 | 0.656667 | 0.660000 | 0.730000 |
| all_evidence_hit@6_errors | 103 | 102 | 81 |
| covered_requirements | 0.656667 | 0.660000 | 0.730000 |
| document_hit@1 | 0.573333 | 0.573333 | 0.686667 |
| document_hit@10 | 0.950000 | 0.950000 | 0.960000 |
| document_hit@3 | 0.806667 | 0.806667 | 0.876667 |
| document_hit@5 | 0.880000 | 0.880000 | 0.933333 |
| document_mrr@10 | 0.703770 | 0.703770 | 0.788545 |
| document_ndcg@10 | 0.763871 | 0.763871 | 0.831088 |
| document_recall@1 | 0.573333 | 0.573333 | 0.686667 |
| document_recall@10 | 0.950000 | 0.950000 | 0.960000 |
| document_recall@3 | 0.806667 | 0.806667 | 0.876667 |
| document_recall@5 | 0.880000 | 0.880000 | 0.933333 |
| evidence_precision | 0.023813 | 0.023929 | 0.026831 |
| evidence_recall@20 | 0.813333 | 0.813333 | 0.813333 |
| evidence_recall@6 | 0.656667 | 0.660000 | 0.730000 |
| gold_requirement_count | 1.000000 | 1.000000 | 1.000000 |
| gold_span_coverage | 0.619917 | 0.622073 | 0.693860 |
| gold_span_coverage@20 | 0.785679 | 0.785679 | 0.785679 |
| gold_span_coverage@6 | 0.619917 | 0.622073 | 0.693860 |
| mrr@10 | 0.510000 | 0.510000 | 0.575319 |
| mrr@5 | 0.693833 | 0.693833 | 0.784444 |
| ndcg@10 | 0.532059 | 0.532059 | 0.597376 |
| ndcg@5 | 0.740636 | 0.740636 | 0.821926 |
| questions | 300 | 300 | 300 |
| ranked_document_count | 9.026667 | 9.026667 | 9.026667 |
| redundancy_ratio | 0.012046 | 0.012046 | 0.005924 |
| requirements_total | 1.000000 | 1.000000 | 1.000000 |
| selected_characters | 3664.216667 | 3661.673333 | 3619.210000 |
| selected_tokens | 651.016667 | 650.576667 | 647.840000 |
| unique_documents | 3.623333 | 3.643333 | 3.310000 |
| median latency (s) | 1.518917 | 0.743863 | 1.210191 |
| index bytes | 113782028 | 113782028 | 113782028 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.05333333333333334 | [0.02, 0.08666666666666667] | 300 |
| evidence_recall@6 | 0.07333333333333333 | [0.03333333333333333, 0.11333333333333333] | 300 |
| all_evidence_hit@6 | 0.07333333333333333 | [0.03333333333333333, 0.11333333333333333] | 300 |
| ndcg@10 | 0.06531704100262944 | [0.029998307933773415, 0.102320955600745] | 300 |
| gold_span_coverage | 0.0739431717994958 | [0.03294299386813287, 0.11460958403024478] | 300 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 21 | 5 | 274 |
| evidence_recall@6 | 32 | 10 | 258 |
| all_evidence_hit@6 | 32 | 10 | 258 |
| ndcg@10 | 104 | 57 | 139 |
| gold_span_coverage | 42 | 14 | 244 |
