# Experiment comparison

| Metric | baseline_dev | hierarchy_h1_dev | hierarchy_h2_dev | hierarchy_h3_dev |
|---|---:|---:|---:|---:|
| all_documents_hit@5 | 1.000000 | 0.933333 | 1.000000 | 1.000000 |
| all_documents_hit@5_errors | 0 | 2 | 0 | 0 |
| all_evidence_hit@20 | 0.933333 | 0.866667 | 0.933333 | 0.933333 |
| all_evidence_hit@6 | 0.833333 | 0.766667 | 0.833333 | 0.833333 |
| all_evidence_hit@6_errors | 5 | 7 | 5 | 5 |
| covered_requirements | 1.060606 | 0.969697 | 1.060606 | 1.060606 |
| document_hit@1 | 0.800000 | 0.800000 | 0.800000 | 0.800000 |
| document_hit@3 | 1.000000 | 0.933333 | 1.000000 | 1.000000 |
| document_hit@5 | 1.000000 | 0.933333 | 1.000000 | 1.000000 |
| document_recall@1 | 0.766667 | 0.766667 | 0.766667 | 0.766667 |
| document_recall@3 | 1.000000 | 0.933333 | 1.000000 | 1.000000 |
| document_recall@5 | 1.000000 | 0.933333 | 1.000000 | 1.000000 |
| evidence_precision | 0.039566 | 0.033121 | 0.039633 | 0.039633 |
| evidence_recall@20 | 0.972222 | 0.894444 | 0.972222 | 0.972222 |
| evidence_recall@6 | 0.894444 | 0.816667 | 0.894444 | 0.894444 |
| gold_requirement_count | 1.242424 | 1.242424 | 1.242424 | 1.242424 |
| gold_span_coverage | 0.894444 | 0.816667 | 0.894444 | 0.894444 |
| gold_span_coverage@20 | 0.972222 | 0.894444 | 0.972222 | 0.972222 |
| gold_span_coverage@6 | 0.894444 | 0.816667 | 0.894444 | 0.894444 |
| mrr@10 | 0.823704 | 0.759815 | 0.823704 | 0.823704 |
| mrr@5 | 0.883333 | 0.861111 | 0.883333 | 0.883333 |
| ndcg@10 | 0.832606 | 0.778291 | 0.832606 | 0.832606 |
| ndcg@5 | 0.913093 | 0.879760 | 0.913093 | 0.913093 |
| questions | 33 | 33 | 33 | 33 |
| ranked_document_count | 5.060606 | 4.424242 | 4.939394 | 4.939394 |
| redundancy_ratio | 0.048245 | 0.036669 | 0.049224 | 0.049224 |
| requirements_total | 1.242424 | 1.242424 | 1.242424 | 1.242424 |
| selected_characters | 2128.060606 | 2109.878788 | 2130.636364 | 2130.636364 |
| selected_tokens | 269.060606 | 264.181818 | 268.636364 | 268.636364 |
| unique_documents | 2.515152 | 2.454545 | 2.545455 | 2.545455 |
| median latency (s) | 0.786365 | 1.401424 | 1.600332 | 1.610904 |
| index bytes | 31009040 | 38386488 | 38386488 | 38386488 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 30 |
| evidence_recall@6 | 0.0 | [0.0, 0.0] | 30 |
| all_evidence_hit@6 | 0.0 | [0.0, 0.0] | 30 |
| ndcg@10 | 0.0 | [0.0, 0.0] | 30 |
| gold_span_coverage | 0.0 | [0.0, 0.0] | 30 |
