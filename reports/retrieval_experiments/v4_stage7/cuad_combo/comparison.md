# Experiment comparison

| Metric | v4_cuad_bge_rerank | v4_cuad_bge_adaptive_rerank |
|---|---:|---:|
| all_documents_hit@5 | 1.000000 | 1.000000 |
| all_documents_hit@5_errors | 0 | 0 |
| all_evidence_hit@20 | 0.600000 | 0.600000 |
| all_evidence_hit@6 | 0.380000 | 0.375000 |
| all_evidence_hit@6_errors | 124 | 125 |
| covered_requirements | 0.730000 | 0.745000 |
| document_hit@1 | 1.000000 | 1.000000 |
| document_hit@10 | 1.000000 | 1.000000 |
| document_hit@3 | 1.000000 | 1.000000 |
| document_hit@5 | 1.000000 | 1.000000 |
| document_mrr@10 | 1.000000 | 1.000000 |
| document_ndcg@10 | 1.000000 | 1.000000 |
| document_recall@1 | 1.000000 | 1.000000 |
| document_recall@10 | 1.000000 | 1.000000 |
| document_recall@3 | 1.000000 | 1.000000 |
| document_recall@5 | 1.000000 | 1.000000 |
| evidence_precision | 0.059099 | 0.059894 |
| evidence_recall@20 | 0.664071 | 0.664071 |
| evidence_recall@6 | 0.451012 | 0.457095 |
| gold_requirement_count | 1.620000 | 1.620000 |
| gold_span_coverage | 0.347108 | 0.354115 |
| gold_span_coverage@20 | 0.539451 | 0.539451 |
| gold_span_coverage@6 | 0.347108 | 0.354115 |
| mrr@10 | 0.272552 | 0.272552 |
| mrr@5 | 1.000000 | 1.000000 |
| ndcg@10 | 0.320018 | 0.320018 |
| ndcg@5 | 1.000000 | 1.000000 |
| questions | 200 | 200 |
| ranked_document_count | 2.405000 | 2.405000 |
| redundancy_ratio | 0.000000 | 0.000000 |
| requirements_total | 1.620000 | 1.620000 |
| selected_characters | 4504.615000 | 4496.745000 |
| selected_tokens | 658.785000 | 659.190000 |
| unique_documents | 1.475000 | 1.540000 |
| median latency (s) | 0.811703 | 2.254988 |
| index bytes | 35629778 | 35629778 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 200 |
| evidence_recall@6 | 0.006083333333333334 | [-0.025333333333333333, 0.03791666666666667] | 200 |
| all_evidence_hit@6 | -0.005 | [-0.035, 0.03] | 200 |
| ndcg@10 | 0.0 | [0.0, 0.0] | 200 |
| gold_span_coverage | 0.0070064669182403165 | [-0.019028436993154763, 0.034305430427700706] | 200 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 0 | 0 | 200 |
| evidence_recall@6 | 9 | 6 | 185 |
| all_evidence_hit@6 | 5 | 6 | 189 |
| ndcg@10 | 0 | 0 | 200 |
| gold_span_coverage | 10 | 6 | 184 |
