# Experiment comparison

| Metric | v3_cuda_miracl_baseline | v3_cuda_miracl_mmr | v3_cuda_miracl_coverage | v3_cuda_miracl_bge_e2 |
|---|---:|---:|---:|---:|
| all_documents_hit@5 | 0.980000 | 0.980000 | 0.980000 | 0.980000 |
| all_documents_hit@5_errors | 1 | 1 | 1 | 1 |
| covered_requirements | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| document_hit@1 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@10 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@3 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@5 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_mrr@10 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_ndcg@10 | 0.999637 | 0.999637 | 0.999637 | 0.999637 |
| document_recall@1 | 0.720667 | 0.720667 | 0.720667 | 0.720667 |
| document_recall@10 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_recall@3 | 0.982000 | 0.982000 | 0.982000 | 0.982000 |
| document_recall@5 | 0.996000 | 0.996000 | 0.996000 | 0.996000 |
| evidence_precision | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| gold_requirement_count | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| mrr@5 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| ndcg@5 | 0.997376 | 0.997376 | 0.997376 | 0.997376 |
| questions | 50 | 50 | 50 | 50 |
| ranked_document_count | 20.000000 | 20.000000 | 20.000000 | 20.000000 |
| redundancy_ratio | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| requirements_total | 0.000000 | 0.000000 | 0.000000 | 0.000000 |
| selected_characters | 4121.040000 | 4150.180000 | 4121.040000 | 4089.480000 |
| selected_tokens | 568.420000 | 571.280000 | 568.420000 | 562.100000 |
| unique_documents | 6.000000 | 6.000000 | 6.000000 | 6.000000 |
| median latency (s) | 0.272757 | 0.211332 | 0.218420 | 0.316047 |
| index bytes | 20377395 | 20377392 | 20377408 | 47540430 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 50 |
| evidence_recall@6 | None | None | 0 |
| all_evidence_hit@6 | None | None | 0 |
| ndcg@10 | None | None | 0 |
| gold_span_coverage | None | None | 0 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 0 | 0 | 50 |
| evidence_recall@6 | 0 | 0 | 0 |
| all_evidence_hit@6 | 0 | 0 | 0 |
| ndcg@10 | 0 | 0 | 0 |
| gold_span_coverage | 0 | 0 | 0 |
