# Experiment comparison

| Metric | v3_cuda_legal_baseline | v3_cuda_legal_mmr | v3_cuda_legal_coverage | v3_cuda_legal_bge_e2 |
|---|---:|---:|---:|---:|
| all_documents_hit@5 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| all_documents_hit@5_errors | 0 | 0 | 0 | 0 |
| all_evidence_hit@20 | 0.510000 | 0.510000 | 0.480000 | 0.600000 |
| all_evidence_hit@6 | 0.120000 | 0.120000 | 0.210000 | 0.165000 |
| all_evidence_hit@6_errors | 176 | 176 | 158 | 167 |
| covered_requirements | 0.225000 | 0.245000 | 0.380000 | 0.315000 |
| document_hit@1 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@10 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@3 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_hit@5 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_mrr@10 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_ndcg@10 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_recall@1 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_recall@10 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_recall@3 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| document_recall@5 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| evidence_precision | 0.018489 | 0.019807 | 0.030356 | 0.022784 |
| evidence_recall@20 | 0.596143 | 0.596143 | 0.561893 | 0.664071 |
| evidence_recall@6 | 0.158750 | 0.169583 | 0.259667 | 0.212667 |
| gold_requirement_count | 1.620000 | 1.620000 | 1.620000 | 1.620000 |
| gold_span_coverage | 0.127303 | 0.126233 | 0.205977 | 0.154638 |
| gold_span_coverage@20 | 0.487929 | 0.487929 | 0.459826 | 0.539451 |
| gold_span_coverage@6 | 0.127303 | 0.126233 | 0.205977 | 0.154638 |
| mrr@10 | 0.102474 | 0.102474 | 0.092276 | 0.111312 |
| mrr@5 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| ndcg@10 | 0.160609 | 0.160609 | 0.128139 | 0.159654 |
| ndcg@5 | 1.000000 | 1.000000 | 1.000000 | 1.000000 |
| questions | 200 | 200 | 200 | 200 |
| ranked_document_count | 3.995000 | 3.995000 | 11.320000 | 2.405000 |
| redundancy_ratio | 0.000780 | 0.000000 | 0.000000 | 0.000000 |
| requirements_total | 1.620000 | 1.620000 | 1.620000 | 1.620000 |
| selected_characters | 4504.695000 | 4519.115000 | 4455.720000 | 4508.045000 |
| selected_tokens | 658.440000 | 658.440000 | 658.965000 | 658.185000 |
| unique_documents | 1.505000 | 1.535000 | 2.320000 | 1.390000 |
| median latency (s) | 0.263069 | 0.153255 | 0.843062 | 0.574874 |
| index bytes | 15112082 | 15112079 | 15112095 | 35629778 |

## Paired bootstrap: last minus baseline

| Metric | Difference | 95% CI | n |
|---|---:|---|---:|
| document_recall@5 | 0.0 | [0.0, 0.0] | 200 |
| evidence_recall@6 | 0.05391666666666667 | [0.02333125, 0.0875] | 200 |
| all_evidence_hit@6 | 0.045 | [0.015, 0.08] | 200 |
| ndcg@10 | -0.0009545975993657172 | [-0.019140261157202333, 0.016880310157654684] | 200 |
| gold_span_coverage | 0.02733447087435075 | [0.0019028563284923994, 0.05459913735219489] | 200 |

## Per-query transitions

| Metric | Improved | Regressed | Unchanged |
|---|---:|---:|---:|
| document_recall@5 | 0 | 0 | 200 |
| evidence_recall@6 | 20 | 3 | 177 |
| all_evidence_hit@6 | 10 | 1 | 189 |
| ndcg@10 | 47 | 45 | 108 |
| gold_span_coverage | 21 | 6 | 173 |
