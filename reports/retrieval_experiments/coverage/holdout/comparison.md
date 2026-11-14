# Experiment comparison

| Metric | baseline_holdout | coverage_mmr_holdout | coverage_decomposed_holdout |
|---|---:|---:|---:|
| all_documents_hit@5 | 1.000000 | 1.000000 | 1.000000 |
| all_documents_hit@5_errors | 0 | 0 | 0 |
| all_evidence_hit@20 | 0.791667 | 0.791667 | 0.833333 |
| all_evidence_hit@6 | 0.791667 | 0.791667 | 0.833333 |
| all_evidence_hit@6_errors | 5 | 5 | 4 |
| covered_requirements | 1.259259 | 1.259259 | 1.407407 |
| document_hit@1 | 0.791667 | 0.791667 | 0.791667 |
| document_hit@3 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@5 | 1.000000 | 1.000000 | 1.000000 |
| document_recall@1 | 0.791667 | 0.791667 | 0.791667 |
| document_recall@3 | 0.979167 | 0.979167 | 0.979167 |
| document_recall@5 | 1.000000 | 1.000000 | 1.000000 |
| evidence_precision | 0.027983 | 0.026403 | 0.029032 |
| evidence_recall@20 | 0.812500 | 0.812500 | 0.868056 |
| evidence_recall@6 | 0.812500 | 0.812500 | 0.868056 |
| gold_requirement_count | 1.629630 | 1.629630 | 1.629630 |
| gold_span_coverage | 0.812500 | 0.812500 | 0.868056 |
| gold_span_coverage@20 | 0.812500 | 0.812500 | 0.868056 |
| gold_span_coverage@6 | 0.812500 | 0.812500 | 0.868056 |
| mrr@10 | 0.743056 | 0.743056 | 0.805556 |
| mrr@5 | 0.888889 | 0.888889 | 0.888889 |
| ndcg@10 | 0.734146 | 0.734146 | 0.806348 |
| ndcg@5 | 0.920598 | 0.920598 | 0.920598 |
| questions | 27 | 27 | 27 |
| ranked_document_count | 5.851852 | 5.851852 | 7.037037 |
| redundancy_ratio | 0.083753 | 0.049177 | 0.076762 |
| requirements_total | 1.629630 | 1.629630 | 1.629630 |
| selected_characters | 2706.407407 | 2680.962963 | 2840.000000 |
| selected_tokens | 330.666667 | 326.962963 | 348.370370 |
| unique_documents | 2.481481 | 2.629630 | 2.629630 |
| median latency (s) | 0.856760 | 2.626949 | 2.762221 |
| index bytes | 31009040 | 31009040 | 31009040 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 24 |
| evidence_recall@6 | 0.05555555555555555 | [0.0, 0.15277777777777776] | 24 |
| all_evidence_hit@6 | 0.041666666666666664 | [0.0, 0.125] | 24 |
| ndcg@10 | 0.07220119251990796 | [0.0, 0.18606905170648258] | 24 |
| gold_span_coverage | 0.05555555555555555 | [0.0, 0.15277777777777776] | 24 |
