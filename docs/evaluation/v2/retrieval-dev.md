# Retrieval evaluation

Status: complete; mode: offline; split: dev

Dataset: `ed221414caa67606ce0576288e3f39fae4e6f7e5bb7e0d2a98ce94e817b1dd5a`; code: `136262f528d0c32e5dc2c35671816f4794cef14b`

| Strategy | n / answerable / negative | R@1 | R@3 | R@5 | R@10 | MRR@10 | Hit@1 / 3 / 5 / 10 | nDCG@10 | P50 / P95 ms | Negative empty accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dense_exact_offline | 80 / 64 / 16 | 0.6797 | 0.8750 | 0.8984 | 0.9375 | 0.8789 | 0.7812 / 0.9844 / 1.0000 / 1.0000 | 0.8520 | 11.3493 / 13.6881 | 0.0000 |
| dense_rerank_offline | 80 / 64 / 16 | 0.8281 | 0.9922 | 1.0000 | 1.0000 | 0.9766 | 0.9531 / 1.0000 / 1.0000 / 1.0000 | 0.9813 | 9908.2023 / 10873.6090 | 0.0000 |

Unavailable strategies: {"dense_pgvector": "PostgreSQL not used in offline mode; no substitute results", "sparse_ts_rank": "PostgreSQL not used in offline mode; no substitute results", "hybrid": "PostgreSQL not used in offline mode; no substitute results", "hybrid_rerank": "PostgreSQL not used in offline mode; no substitute results"}

Binary chunk relevance. Recall divides by ALL labeled relevant chunks; Hit is any hit; MRR is first relevant reciprocal rank at 10; nDCG uses binary gain and ideal min(10, |relevant|). Duplicates consume slots and receive credit once. Macro averages exclude unanswerable queries. Negative accuracy is empty-result detection only, not semantic refusal.

P50/P95: linear interpolation on warm per-query pipeline time; includes query encoding; excludes corpus encoding/model loading. Shared query encoding time is charged to every strategy. Single sequential run; not an HTTP/concurrency benchmark.

## Failures (all individual rows and local traces in JSON)

| Case | Strategy | Category | Recall@10 | Scope violations |
| --- | --- | --- | --- | --- |
| Q005 | dense_exact_offline | unanswerable | N/A | 0 |
| Q005 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q006 | dense_exact_offline | unanswerable | N/A | 0 |
| Q006 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q013 | dense_exact_offline | multi_evidence | 0.5 | 0 |
| Q014 | dense_exact_offline | boundary | N/A | 0 |
| Q014 | dense_rerank_offline | boundary | N/A | 0 |
| Q021 | dense_exact_offline | unanswerable | N/A | 0 |
| Q021 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q026 | dense_exact_offline | unanswerable | N/A | 0 |
| Q026 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q028 | dense_exact_offline | multi_evidence | 0.5 | 0 |
| Q031 | dense_exact_offline | multi_evidence | 0.5 | 0 |
| Q032 | dense_exact_offline | multi_evidence | 0.5 | 0 |
| Q038 | dense_exact_offline | multi_evidence | 0.5 | 0 |
| Q061 | dense_exact_offline | multi_evidence | 0.5 | 0 |
| Q065 | dense_exact_offline | boundary | N/A | 0 |
| Q065 | dense_rerank_offline | boundary | N/A | 0 |
| Q066 | dense_exact_offline | unanswerable | N/A | 0 |
| Q066 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q067 | dense_exact_offline | unanswerable | N/A | 0 |
| Q067 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q075 | dense_exact_offline | unanswerable | N/A | 0 |
| Q075 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q078 | dense_exact_offline | unanswerable | N/A | 0 |
| Q078 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q079 | dense_exact_offline | unanswerable | N/A | 0 |
| Q079 | dense_rerank_offline | unanswerable | N/A | 0 |
| Q080 | dense_exact_offline | boundary | N/A | 0 |
| Q080 | dense_rerank_offline | boundary | N/A | 0 |
| Q082 | dense_exact_offline | boundary | N/A | 0 |
| Q082 | dense_rerank_offline | boundary | N/A | 0 |
| Q085 | dense_exact_offline | boundary | N/A | 0 |
| Q085 | dense_rerank_offline | boundary | N/A | 0 |
| Q091 | dense_exact_offline | multi_evidence | 0.5 | 0 |
| Q092 | dense_exact_offline | multi_evidence | 0.5 | 0 |
| Q095 | dense_exact_offline | boundary | N/A | 0 |
| Q095 | dense_rerank_offline | boundary | N/A | 0 |
| Q097 | dense_exact_offline | unanswerable | N/A | 0 |
| Q097 | dense_rerank_offline | unanswerable | N/A | 0 |
