# Experiment comparison

| Metric | baseline_dev | stable_dev |
|---|---:|---:|
| all_documents_hit@5 | 1.000000 | 1.000000 |
| all_documents_hit@5_errors | 0 | 0 |
| all_evidence_hit@20 | 0.933333 | 0.933333 |
| all_evidence_hit@6 | 0.833333 | 0.866667 |
| all_evidence_hit@6_errors | 5 | 4 |
| covered_requirements | 1.060606 | 1.121212 |
| document_hit@1 | 0.800000 | 0.800000 |
| document_hit@10 | — | 1.000000 |
| document_hit@3 | 1.000000 | 1.000000 |
| document_hit@5 | 1.000000 | 1.000000 |
| document_mrr@10 | — | 0.883333 |
| document_ndcg@10 | — | 0.913093 |
| document_recall@1 | 0.766667 | 0.766667 |
| document_recall@10 | — | 1.000000 |
| document_recall@3 | 1.000000 | 1.000000 |
| document_recall@5 | 1.000000 | 1.000000 |
| evidence_precision | 0.039566 | 0.041967 |
| evidence_recall@20 | 0.972222 | 0.972222 |
| evidence_recall@6 | 0.894444 | 0.922222 |
| gold_requirement_count | 1.242424 | 1.242424 |
| gold_span_coverage | 0.894444 | 0.922222 |
| gold_span_coverage@20 | 0.972222 | 0.972222 |
| gold_span_coverage@6 | 0.894444 | 0.922222 |
| mrr@10 | 0.823704 | 0.823704 |
| mrr@5 | 0.883333 | 0.883333 |
| ndcg@10 | 0.832606 | 0.821637 |
| ndcg@5 | 0.913093 | 0.913093 |
| questions | 33 | 33 |
| ranked_document_count | 5.060606 | 6.212121 |
| redundancy_ratio | 0.048245 | 0.042760 |
| requirements_total | 1.242424 | 1.242424 |
| selected_characters | 2128.060606 | 2104.424242 |
| selected_tokens | 269.060606 | 266.121212 |
| unique_documents | 2.515152 | 2.545455 |
| median latency (s) | 0.786365 | 0.893688 |
| index bytes | 31009040 | 31009040 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 30 |
| evidence_recall@6 | 0.027777777777777776 | [0.0, 0.0668055555555548] | 30 |
| all_evidence_hit@6 | 0.03333333333333333 | [0.0, 0.1] | 30 |
| ndcg@10 | -0.010969279234990621 | [-0.027161787450757893, 0.0] | 30 |
| gold_span_coverage | 0.027777777777777776 | [0.0, 0.0668055555555548] | 30 |
