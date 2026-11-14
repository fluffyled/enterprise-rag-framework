# Experiment comparison

| Metric | baseline_holdout | coverage_decomposed_holdout | bge_e2_holdout |
|---|---:|---:|---:|
| all_documents_hit@5 | 1.000000 | 1.000000 | 1.000000 |
| all_documents_hit@5_errors | 0 | 0 | 0 |
| all_evidence_hit@20 | 0.791667 | 0.833333 | 0.791667 |
| all_evidence_hit@6 | 0.791667 | 0.833333 | 0.791667 |
| all_evidence_hit@6_errors | 5 | 4 | 5 |
| covered_requirements | 1.259259 | 1.407407 | 1.407407 |
| document_hit@1 | 0.791667 | 0.791667 | 0.750000 |
| document_hit@10 | — | — | 1.000000 |
| document_hit@3 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@5 | 1.000000 | 1.000000 | 1.000000 |
| document_mrr@10 | — | — | 0.868056 |
| document_ndcg@10 | — | — | 0.905220 |
| document_recall@1 | 0.791667 | 0.791667 | 0.750000 |
| document_recall@10 | — | — | 1.000000 |
| document_recall@3 | 0.979167 | 0.979167 | 0.979167 |
| document_recall@5 | 1.000000 | 1.000000 | 1.000000 |
| evidence_precision | 0.027983 | 0.029032 | 0.028226 |
| evidence_recall@20 | 0.812500 | 0.868056 | 0.868056 |
| evidence_recall@6 | 0.812500 | 0.868056 | 0.868056 |
| gold_requirement_count | 1.629630 | 1.629630 | 1.629630 |
| gold_span_coverage | 0.812500 | 0.868056 | 0.868056 |
| gold_span_coverage@20 | 0.812500 | 0.868056 | 0.868056 |
| gold_span_coverage@6 | 0.812500 | 0.868056 | 0.868056 |
| mrr@10 | 0.743056 | 0.805556 | 0.784722 |
| mrr@5 | 0.888889 | 0.888889 | 0.868056 |
| ndcg@10 | 0.734146 | 0.806348 | 0.788676 |
| ndcg@5 | 0.920598 | 0.920598 | 0.905220 |
| questions | 27 | 27 | 27 |
| ranked_document_count | 5.851852 | 7.037037 | 4.555556 |
| redundancy_ratio | 0.083753 | 0.076762 | 0.095306 |
| requirements_total | 1.629630 | 1.629630 | 1.629630 |
| selected_characters | 2706.407407 | 2840.000000 | 3286.629630 |
| selected_tokens | 330.666667 | 348.370370 | 397.814815 |
| unique_documents | 2.481481 | 2.629630 | 2.185185 |
| median latency (s) | 0.856760 | 2.762221 | 1.153434 |
| index bytes | 31009040 | 31009040 | 78555717 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 24 |
| evidence_recall@6 | 0.05555555555555555 | [0.0, 0.13888888888888887] | 24 |
| all_evidence_hit@6 | 0.0 | [0.0, 0.0] | 24 |
| ndcg@10 | 0.0545300455492452 | [-0.029636253460574594, 0.16666666666666666] | 24 |
| gold_span_coverage | 0.05555555555555555 | [0.0, 0.13888888888888887] | 24 |
