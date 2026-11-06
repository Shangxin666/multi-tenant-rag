# Retrieval evaluation

Status: complete; mode: offline; split: final

Dataset: `ed221414caa67606ce0576288e3f39fae4e6f7e5bb7e0d2a98ce94e817b1dd5a`; code: `136262f528d0c32e5dc2c35671816f4794cef14b`

| Strategy | n / answerable / negative | R@1 | R@3 | R@5 | R@10 | MRR@10 | Hit@1 / 3 / 5 / 10 | nDCG@10 | P50 / P95 ms | Negative empty accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dense_exact_offline | 40 / 32 / 8 | 0.7344 | 0.8281 | 0.9062 | 1.0000 | 0.8979 | 0.8438 / 0.9375 / 1.0000 / 1.0000 | 0.8830 | 10.3085 / 11.8509 | 0.0000 |
| dense_rerank_offline | 40 / 32 / 8 | 0.8281 | 1.0000 | 1.0000 | 1.0000 | 0.9688 | 0.9375 / 1.0000 / 1.0000 / 1.0000 | 0.9769 | 8328.2774 / 9608.3049 | 0.0000 |

Unavailable strategies: {"dense_pgvector": "PostgreSQL not used in offline mode; no substitute results", "sparse_ts_rank": "PostgreSQL not used in offline mode; no substitute results", "hybrid": "PostgreSQL not used in offline mode; no substitute results", "hybrid_rerank": "PostgreSQL not used in offline mode; no substitute results"}

Binary chunk relevance. Recall divides by ALL labeled relevant chunks; Hit is any hit; MRR is first relevant reciprocal rank at 10; nDCG uses binary gain and ideal min(10, |relevant|). Duplicates consume slots and receive credit once. Macro averages exclude unanswerable queries. Negative accuracy is empty-result detection only, not semantic refusal.

P50/P95: linear interpolation on warm per-query pipeline time; includes query encoding; excludes corpus encoding/model loading. Shared query encoding time is charged to every strategy. Single sequential run; not an HTTP/concurrency benchmark.

## Failures (all individual rows and local traces in JSON)

| Case | Strategy | Category | Recall@10 | Scope violations |
| --- | --- | --- | --- | --- |
| Q046 | dense_exact_offline | boundary | N/A | 0 |
| Q046 | dense_rerank_offline | boundary | N/A | 0 |
| Q051 | dense_exact_offline | boundary | N/A | 0 |
| Q051 | dense_rerank_offline | boundary | N/A | 0 |
| Q057 | dense_exact_offline | boundary | N/A | 0 |
| Q057 | dense_rerank_offline | boundary | N/A | 0 |
| Q058 | dense_exact_offline | boundary | N/A | 0 |
| Q058 | dense_rerank_offline | boundary | N/A | 0 |
| Q102 | dense_exact_offline | unanswerable | N/A | 0 |
| Q102 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q107 | dense_exact_offline | boundary | N/A | 0 |
| Q107 | dense_rerank_offline | boundary | N/A | 0 |
| Q110 | dense_exact_offline | unanswerable | N/A | 0 |
| Q110 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q111 | dense_exact_offline | boundary | N/A | 0 |
| Q111 | dense_rerank_offline | boundary | N/A | 0 |
