# Retrieval evaluation

Status: failed; mode: postgres; split: dev

Dataset: `ed221414caa67606ce0576288e3f39fae4e6f7e5bb7e0d2a98ce94e817b1dd5a`; code: `136262f528d0c32e5dc2c35671816f4794cef14b`

| Strategy | n / answerable / negative | R@1 | R@3 | R@5 | R@10 | MRR@10 | Hit@1 / 3 / 5 / 10 | nDCG@10 | P50 / P95 ms | Negative empty accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Unavailable strategies: {}

Binary chunk relevance. Recall divides by ALL labeled relevant chunks; Hit is any hit; MRR is first relevant reciprocal rank at 10; nDCG uses binary gain and ideal min(10, |relevant|). Duplicates consume slots and receive credit once. Macro averages exclude unanswerable queries. Negative accuracy is empty-result detection only, not semantic refusal.

P50/P95: linear interpolation on warm per-query pipeline time; includes query encoding; excludes corpus encoding/model loading. Shared query encoding time is charged to every strategy. Single sequential run; not an HTTP/concurrency benchmark.

## Failures (all individual rows and local traces in JSON)

| Case | Strategy | Category | Recall@10 | Scope violations |
| --- | --- | --- | --- | --- |

Error: ConnectionRefusedError
