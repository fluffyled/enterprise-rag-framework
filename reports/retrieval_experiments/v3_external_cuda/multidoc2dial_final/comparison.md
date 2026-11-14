# Experiment comparison

| Metric | v3_cuda_multidoc_baseline | v3_cuda_multidoc_final |
|---|---:|---:|
| all_documents_hit@5 | 0.880000 | 0.843333 |
| all_documents_hit@5_errors | 36 | 47 |
| all_evidence_hit@20 | 0.823333 | 0.823333 |
| all_evidence_hit@6 | 0.666667 | 0.636667 |
| all_evidence_hit@6_errors | 100 | 109 |
| covered_requirements | 0.666667 | 0.636667 |
| document_hit@1 | 0.536667 | 0.530000 |
| document_hit@10 | 0.960000 | 0.926667 |
| document_hit@3 | 0.793333 | 0.763333 |
| document_hit@5 | 0.880000 | 0.843333 |
| document_mrr@10 | 0.683222 | 0.663583 |
| document_ndcg@10 | 0.750708 | 0.727372 |
| document_recall@1 | 0.536667 | 0.530000 |
| document_recall@10 | 0.960000 | 0.926667 |
| document_recall@3 | 0.793333 | 0.763333 |
| document_recall@5 | 0.880000 | 0.843333 |
| evidence_precision | 0.024132 | 0.022977 |
| evidence_recall@20 | 0.823333 | 0.823333 |
| evidence_recall@6 | 0.666667 | 0.636667 |
| gold_requirement_count | 1.000000 | 1.000000 |
| gold_span_coverage | 0.637187 | 0.602602 |
| gold_span_coverage@20 | 0.800457 | 0.789290 |
| gold_span_coverage@6 | 0.637187 | 0.602602 |
| mrr@10 | 0.498496 | 0.500884 |
| mrr@5 | 0.672000 | 0.652222 |
| ndcg@10 | 0.531095 | 0.516364 |
| ndcg@5 | 0.724288 | 0.700172 |
| questions | 300 | 300 |
| ranked_document_count | 10.036667 | 19.490000 |
| redundancy_ratio | 0.022071 | 0.024564 |
| requirements_total | 1.000000 | 1.000000 |
| selected_characters | 3619.713333 | 3619.306667 |
| selected_tokens | 642.816667 | 641.370000 |
| unique_documents | 3.813333 | 3.943333 |
| median latency (s) | 0.403225 | 0.278267 |
| index bytes | 48234547 | 48234559 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | -0.03666666666666667 | [-0.07, -0.006666666666666667] | 300 |
| evidence_recall@6 | -0.03 | [-0.06674999999999999, 0.01] | 300 |
| all_evidence_hit@6 | -0.03 | [-0.06674999999999999, 0.01] | 300 |
| ndcg@10 | -0.014730527630285055 | [-0.037717275657691195, 0.01146918178310858] | 300 |
| gold_span_coverage | -0.034585228959486486 | [-0.07201172882334213, 0.0022609192300114154] | 300 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 6 | 17 | 277 |
| evidence_recall@6 | 15 | 24 | 261 |
| all_evidence_hit@6 | 15 | 24 | 261 |
| ndcg@10 | 19 | 94 | 187 |
| gold_span_coverage | 15 | 26 | 259 |
