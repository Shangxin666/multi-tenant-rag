# Retrieval evaluation

Status: complete; mode: offline; split: dev

Dataset: `4829be34987e45c6fda41b50c1999b5c5a92d44cbe41d0c9152bfbf473f3d440`; code: `136262f528d0c32e5dc2c35671816f4794cef14b`

| Strategy | n / answerable / negative | R@1 | R@3 | R@5 | R@10 | MRR@10 | Hit@1 / 3 / 5 / 10 | nDCG@10 | P50 / P95 ms | Negative empty accuracy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dense_exact_offline | 29 / 24 / 5 | 0.1143 | 0.2820 | 0.4307 | 0.6195 | 0.5469 | 0.4167 / 0.5833 / 0.7500 / 0.8750 | 0.4786 | 11.0853 / 13.6837 | 0.0000 |
| dense_rerank_offline | 29 / 24 / 5 | 0.2069 | 0.5198 | 0.6425 | 0.7547 | 0.7500 | 0.6250 / 0.9167 / 0.9167 / 0.9167 | 0.6586 | 6352.0244 / 6622.6470 | 0.0000 |

Unavailable strategies: {"dense_pgvector": "PostgreSQL not used in offline mode; no substitute results", "sparse_ts_rank": "PostgreSQL not used in offline mode; no substitute results", "hybrid": "PostgreSQL not used in offline mode; no substitute results", "hybrid_rerank": "PostgreSQL not used in offline mode; no substitute results"}

Binary chunk relevance. Recall divides by ALL labeled relevant chunks; Hit is any hit; MRR is first relevant reciprocal rank at 10; nDCG uses binary gain and ideal min(10, |relevant|). Duplicates consume slots and receive credit once. Macro averages exclude unanswerable queries. Negative accuracy is empty-result detection only, not semantic refusal.

P50/P95: linear interpolation on warm per-query pipeline time; includes query encoding; excludes corpus encoding/model loading. Shared query encoding time is charged to every strategy. Single sequential run; not an HTTP/concurrency benchmark.

## Failures (all individual rows and local traces in JSON)

| Case | Strategy | Category | Recall@10 | Scope violations |
| --- | --- | --- | --- | --- |
| VUE002 | dense_exact_offline | exact | 0.0 | 0 |
| VUE004 | dense_exact_offline | multi_fact_async_boundary | 0.6666666666666666 | 0 |
| VUE004 | dense_rerank_offline | multi_fact_async_boundary | 0.6666666666666666 | 0 |
| VUE005 | dense_exact_offline | exact | 0.5 | 0 |
| VUE005 | dense_rerank_offline | exact | 0.5 | 0 |
| VUE006 | dense_exact_offline | paraphrase | 0.5 | 0 |
| VUE007 | dense_exact_offline | paraphrase | 0.3333333333333333 | 0 |
| VUE007 | dense_rerank_offline | paraphrase | 0.3333333333333333 | 0 |
| VUE008 | dense_exact_offline | paraphrase | 0.6666666666666666 | 0 |
| VUE010 | dense_exact_offline | paraphrase | 0.5 | 0 |
| VUE011 | dense_exact_offline | multi_evidence | 0.0 | 0 |
| VUE011 | dense_rerank_offline | multi_evidence | 0.0 | 0 |
| VUE012 | dense_exact_offline | multi_evidence | 0.2857142857142857 | 0 |
| VUE012 | dense_rerank_offline | multi_evidence | 0.42857142857142855 | 0 |
| VUE013 | dense_exact_offline | multi_evidence | 0.8 | 0 |
| VUE014 | dense_exact_offline | multi_evidence | 0.4 | 0 |
| VUE014 | dense_rerank_offline | multi_evidence | 0.6 | 0 |
| VUE015 | dense_exact_offline | multi_evidence | 0.75 | 0 |
| VUE015 | dense_rerank_offline | multi_evidence | 0.5 | 0 |
| VUE017 | dense_exact_offline | similar_concepts | 0.8 | 0 |
| VUE018 | dense_rerank_offline | similar_concepts | 1.0 | 0 |
| VUE019 | dense_exact_offline | similar_concepts | 0.5 | 0 |
| VUE019 | dense_rerank_offline | similar_concepts | 0.75 | 0 |
| VUE020 | dense_exact_offline | similar_concepts | 0.6666666666666666 | 0 |
| VUE020 | dense_rerank_offline | similar_concepts | 0.8333333333333334 | 0 |
| VUE021 | dense_exact_offline | unanswerable | N/A | 0 |
| VUE021 | dense_rerank_offline | unanswerable | N/A | 0 |
| VUE022 | dense_exact_offline | unanswerable | N/A | 0 |
| VUE022 | dense_rerank_offline | unanswerable | N/A | 0 |
| VUE023 | dense_exact_offline | unanswerable | N/A | 0 |
| VUE023 | dense_rerank_offline | unanswerable | N/A | 0 |
| VUE024 | dense_exact_offline | unanswerable | N/A | 0 |
| VUE024 | dense_rerank_offline | unanswerable | N/A | 0 |
| VUE025 | dense_exact_offline | unanswerable | N/A | 0 |
| VUE025 | dense_rerank_offline | unanswerable | N/A | 0 |
| VUE027 | dense_exact_offline | version_boundary | 0.0 | 0 |
| VUE027 | dense_rerank_offline | version_boundary | 0.0 | 0 |
| VUE028 | dense_rerank_offline | version_boundary | 1.0 | 0 |
| VUE029 | dense_exact_offline | version_boundary | 0.5 | 0 |
| VUE029 | dense_rerank_offline | version_boundary | 0.5 | 0 |

## Exploratory / unverified — not independent Final or human gold

开发探索；VUE026 排除；未改任何人工审核状态。相关 Chunk 标注尚未穷尽，指标仅相对于当前候选标签。
无答案样本不进入 Recall/MRR/nDCG/证据组覆盖率分母。空结果率不是最终回答拒答正确率。
离线 NumPy 精确余弦，不使用 PostgreSQL；无 LLM。单次顺序 CPU 实验，无调参、无 HTTP/并发基准。

| Strategy | EGC@1 | EGC@3 | EGC@5 | EGC@10 |
| --- | ---: | ---: | ---: | ---: |
| dense_exact_offline | 0.3160 | 0.5069 | 0.6736 | 0.8333 |
| dense_rerank_offline | 0.4097 | 0.7743 | 0.8611 | 0.9028 |

## Stage timing (milliseconds)

Query 编码和 Dense 结果在两策略间共享测量；Rerank 总耗时累加这两段和实际重排耗时。冷加载/语料编码及报告写入不计入逐题时间。

| Strategy | Stage | P50 | P95 |
| --- | --- | ---: | ---: |
| dense_exact_offline | query_embedding | 10.528 | 13.216 |
| dense_exact_offline | dense_search | 0.500 | 0.648 |
| dense_exact_offline | cross_encoder_rerank | 0.000 | 0.000 |
| dense_rerank_offline | query_embedding | 10.528 | 13.216 |
| dense_rerank_offline | dense_search | 0.500 | 0.648 |
| dense_rerank_offline | cross_encoder_rerank | 6339.126 | 6609.657 |

## Per-query ranks and metrics

### VUE001 / dense_exact_offline

我改完 count 就去读页面上的数字，拿到的还是旧值。Vue 里应该等哪个时机，代码怎么写？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 0.25, "ndcg@10": 0.46845052016107697}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 0.5, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.015399991767481, "dense_search": 1.0946000111289322, "cross_encoder_rerank": 0.0}
Top10: 1:7b6df58f-aded-5fa8-986d-6c7e5508e301, 2:9b9c4f46-b134-59db-b70e-d22df5725d4a, 3:cfb3ff2a-4f17-5b20-ac88-58a49a34e68c, 4:720f300d-f184-5069-9ad2-3aafb122b8cc, 5:e7a3fae7-1aef-535c-b29e-a3b5a619b3bd, 6:bdbc32a5-5f53-5bb3-892f-2ee0548f42ad, 7:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 8:6de695b5-bfb1-5551-a68b-6571df8d5ff0, 9:b07bb7eb-e560-55c3-bb02-8d7fcb5130b5, 10:3c4d3fe0-ef6c-5163-bbbe-e5de1f6adf2d
Failures: none

### VUE001 / dense_rerank_offline

我改完 count 就去读页面上的数字，拿到的还是旧值。Vue 里应该等哪个时机，代码怎么写？

Metrics: {"recall@1": 0.5, "hit_rate@1": 1.0, "recall@3": 1.0, "hit_rate@3": 1.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 1.0}
Evidence groups: {"evidence_group_coverage@1": 0.5, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.015399991767481, "dense_search": 1.0946000111289322, "cross_encoder_rerank": 6356.330300011905}
Top10: 1:720f300d-f184-5069-9ad2-3aafb122b8cc, 2:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 3:7b6df58f-aded-5fa8-986d-6c7e5508e301, 4:e7a3fae7-1aef-535c-b29e-a3b5a619b3bd, 5:9a542f68-9eb0-5969-ac62-1b5f90ee00ad, 6:cfb3ff2a-4f17-5b20-ac88-58a49a34e68c, 7:b07bb7eb-e560-55c3-bb02-8d7fcb5130b5, 8:6426ad40-dfce-56a0-a538-b258af5ca11e, 9:6e72d545-de1b-5695-9831-10fcdb824335, 10:da2603d2-7929-5ce3-9217-cd86ad3f2955
Failures: none

### VUE002 / dense_exact_offline

模板里反复用同一个计算结果，用 computed 和直接调用方法有什么实际区别？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.0, "hit_rate@5": 0.0, "recall@10": 0.0, "hit_rate@10": 0.0, "mrr@10": 0.0, "ndcg@10": 0.0}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 0.0, "evidence_group_coverage@10": 0.0}
Stage ms: {"query_embedding": 10.328699980163947, "dense_search": 0.5499999970197678, "cross_encoder_rerank": 0.0}
Top10: 1:1bbe5952-a953-5a71-8973-d627be6ae29d, 2:2b5b6baf-ae41-5459-b831-4809597c7b4b, 3:da91b8dd-87b7-56c9-b189-d662360d8d3d, 4:8d4ceeb0-c34c-577b-9c08-09b6bc44f28d, 5:10755dfd-e2a7-5b7c-87ed-ac36aba38fc3, 6:d7a5f209-8d1f-5b7d-8359-58c349c76e59, 7:bd25d6f5-da4c-58c1-8947-f810071a1b1b, 8:97333d3a-4c97-5ddf-b170-a0aea786c63d, 9:e2c6de63-aa2a-5dd8-96d3-4a35dd8951d8, 10:bf02ccc6-915f-583e-9f67-fcbf7f74af46
Failures: labeled_relevant_chunks_missing_at_10, necessary_evidence_groups_uncovered_at_10

### VUE002 / dense_rerank_offline

模板里反复用同一个计算结果，用 computed 和直接调用方法有什么实际区别？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 1.0, "hit_rate@3": 1.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 0.3333333333333333, "ndcg@10": 0.5}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.328699980163947, "dense_search": 0.5499999970197678, "cross_encoder_rerank": 6270.5270999867935}
Top10: 1:2b5b6baf-ae41-5459-b831-4809597c7b4b, 2:10755dfd-e2a7-5b7c-87ed-ac36aba38fc3, 3:311e4473-3182-5dcf-82cd-9e855bf2c846, 4:d7a5f209-8d1f-5b7d-8359-58c349c76e59, 5:e2c6de63-aa2a-5dd8-96d3-4a35dd8951d8, 6:3056d53e-be45-5cf7-92fe-4e81c399cb4a, 7:9a542f68-9eb0-5969-ac62-1b5f90ee00ad, 8:97333d3a-4c97-5ddf-b170-a0aea786c63d, 9:7a9e2078-d610-5ca9-9c0d-824bd581d161, 10:1c6906ee-9f65-5463-8a09-0c1e1f83e9d9
Failures: none

### VUE003 / dense_exact_offline

孙组件 emit 了 save，爷爷组件直接写 @save 为什么收不到？组件事件不是也会冒泡吗？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 0.25, "ndcg@10": 0.43067655807339306}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.24670000676997, "dense_search": 0.4239999980200082, "cross_encoder_rerank": 0.0}
Top10: 1:8f0a5fb6-3b42-52cb-b0a0-91ce2e5ae0f5, 2:7ad21482-7a99-5298-b491-e4c038d091ed, 3:e7e2ac01-9973-5bf5-8b09-ca6066bc3f9a, 4:8ac182f3-5001-5e2e-be32-96cff001c95c, 5:3b0f0264-6b3a-5091-9c44-ba77aa88f80b, 6:e3ec6430-bcd3-5a34-9828-2bf073424e81, 7:f77c7aa6-62a8-5287-97ca-f2251684cf0c, 8:c312fa6b-944d-5ab9-8ca4-fad72d12422c, 9:90bda472-1d76-59a5-9be1-f3b3765b6d0b, 10:af17e069-2291-5e66-ab9e-3e461f361655
Failures: none

### VUE003 / dense_rerank_offline

孙组件 emit 了 save，爷爷组件直接写 @save 为什么收不到？组件事件不是也会冒泡吗？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 1.0, "hit_rate@3": 1.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 0.5, "ndcg@10": 0.6309297535714575}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.24670000676997, "dense_search": 0.4239999980200082, "cross_encoder_rerank": 6187.7564000023995}
Top10: 1:7ad21482-7a99-5298-b491-e4c038d091ed, 2:8ac182f3-5001-5e2e-be32-96cff001c95c, 3:e7e2ac01-9973-5bf5-8b09-ca6066bc3f9a, 4:8f0a5fb6-3b42-52cb-b0a0-91ce2e5ae0f5, 5:f77c7aa6-62a8-5287-97ca-f2251684cf0c, 6:8fec4a85-79b0-509b-bd2c-72500dcd0bfc, 7:90bda472-1d76-59a5-9be1-f3b3765b6d0b, 8:3b0f0264-6b3a-5091-9c44-ba77aa88f80b, 9:c312fa6b-944d-5ab9-8ca4-fad72d12422c, 10:3cefba0f-0104-5d34-9885-b417bf805279
Failures: none

### VUE004 / dense_exact_offline

在普通 setup() 中，我把 onMounted 注册放进接口 Promise.then 回调或 setTimeout 回调里，这样为什么不行？它与 script setup 中顶层 await 后调用组合式 API 的情况有什么区别？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.3333333333333333, "hit_rate@3": 1.0, "recall@5": 0.3333333333333333, "hit_rate@5": 1.0, "recall@10": 0.6666666666666666, "hit_rate@10": 1.0, "mrr@10": 0.5, "ndcg@10": 0.431733884398313}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.6666666666666666, "evidence_group_coverage@5": 0.6666666666666666, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 11.013200011802837, "dense_search": 0.44150001485832036, "cross_encoder_rerank": 0.0}
Top10: 1:7a9e2078-d610-5ca9-9c0d-824bd581d161, 2:70ea2dc7-cd64-584f-a91f-a91c4cc6e9ff, 3:3769516e-964b-55cd-ad0e-2035bcfdef73, 4:6c6a0da9-16b7-505e-a86f-e4c448a3a84f, 5:303a5d7e-3e46-5e10-ac60-549693aa26c3, 6:c7b47ae6-8420-5a95-bc01-6da459d19e30, 7:1c6906ee-9f65-5463-8a09-0c1e1f83e9d9, 8:714936ce-6406-554d-b973-2a203298dc6f, 9:49c99c25-2bc8-5160-b8db-4d67c728b3c7, 10:0c637b1f-991e-5d17-9162-91456a434925
Failures: labeled_relevant_chunks_missing_at_10

### VUE004 / dense_rerank_offline

在普通 setup() 中，我把 onMounted 注册放进接口 Promise.then 回调或 setTimeout 回调里，这样为什么不行？它与 script setup 中顶层 await 后调用组合式 API 的情况有什么区别？

Metrics: {"recall@1": 0.3333333333333333, "hit_rate@1": 1.0, "recall@3": 0.3333333333333333, "hit_rate@3": 1.0, "recall@5": 0.6666666666666666, "hit_rate@5": 1.0, "recall@10": 0.6666666666666666, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.6508205185601091}
Evidence groups: {"evidence_group_coverage@1": 0.3333333333333333, "evidence_group_coverage@3": 0.3333333333333333, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 11.013200011802837, "dense_search": 0.44150001485832036, "cross_encoder_rerank": 6386.6899000131525}
Top10: 1:0c637b1f-991e-5d17-9162-91456a434925, 2:303a5d7e-3e46-5e10-ac60-549693aa26c3, 3:4f39a83a-2200-5b6d-ac29-cbf29f3495f7, 4:ab4c8ce4-1a30-5392-8ba9-9b7474e8fad5, 5:70ea2dc7-cd64-584f-a91f-a91c4cc6e9ff, 6:6c6a0da9-16b7-505e-a86f-e4c448a3a84f, 7:c7b47ae6-8420-5a95-bc01-6da459d19e30, 8:312f7e93-4108-55d5-b002-f76890c5bb39, 9:9727377d-866a-536a-87cf-8b81720723dc, 10:912be6b3-bf0c-52fa-b084-b32a071bda9b
Failures: labeled_relevant_chunks_missing_at_10

### VUE005 / dense_exact_offline

组件现在有 header 和 main 两个根节点，父组件传的 class 不知道落哪儿，还报了警告，要怎么处理？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 0.5, "hit_rate@10": 1.0, "mrr@10": 0.2, "ndcg@10": 0.23719771276929622}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.786800005007535, "dense_search": 0.5008000007364899, "cross_encoder_rerank": 0.0}
Top10: 1:24112c6d-aa7e-5f69-9bdc-2127f4042050, 2:a37087d2-101e-5332-8eb4-8ad4f81c8caf, 3:af17e069-2291-5e66-ab9e-3e461f361655, 4:7ad21482-7a99-5298-b491-e4c038d091ed, 5:50476fce-cc56-5fb7-85b8-c4b220f7cc0c, 6:f7de642c-8c51-5935-b29d-e813ff85d667, 7:f77c7aa6-62a8-5287-97ca-f2251684cf0c, 8:0c2207d5-de26-5f3a-b29d-73abfe744f0b, 9:51c8b1a3-8503-51f0-83a3-06c32e7cd952, 10:bd25d6f5-da4c-58c1-8947-f810071a1b1b
Failures: labeled_relevant_chunks_missing_at_10

### VUE005 / dense_rerank_offline

组件现在有 header 和 main 两个根节点，父组件传的 class 不知道落哪儿，还报了警告，要怎么处理？

Metrics: {"recall@1": 0.5, "hit_rate@1": 1.0, "recall@3": 0.5, "hit_rate@3": 1.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 0.5, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.6131471927654584}
Evidence groups: {"evidence_group_coverage@1": 1.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.786800005007535, "dense_search": 0.5008000007364899, "cross_encoder_rerank": 6412.044299999252}
Top10: 1:50476fce-cc56-5fb7-85b8-c4b220f7cc0c, 2:a37087d2-101e-5332-8eb4-8ad4f81c8caf, 3:41d181fa-3b4a-5220-ad1e-9dc62578993b, 4:7ad21482-7a99-5298-b491-e4c038d091ed, 5:f77c7aa6-62a8-5287-97ca-f2251684cf0c, 6:24112c6d-aa7e-5f69-9bdc-2127f4042050, 7:bbe82e73-5859-5184-8e83-0f1bffd843e0, 8:bf9cd212-476d-5496-8800-b97f88ca327c, 9:af17e069-2291-5e66-ab9e-3e461f361655, 10:c312fa6b-944d-5ab9-8ca4-fad72d12422c
Failures: labeled_relevant_chunks_missing_at_10

### VUE006 / dense_exact_offline

watch(obj.count, ...) 一直没按预期触发，我只想盯着 count，不想监控整个对象，该怎么改？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 0.5, "hit_rate@10": 1.0, "mrr@10": 0.2, "ndcg@10": 0.23719771276929622}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.871099988231435, "dense_search": 0.43120002374053, "cross_encoder_rerank": 0.0}
Top10: 1:eb733fbd-8a4c-595e-bebe-6f8c374b6aca, 2:e788e5c1-ee63-5e5b-a656-42f846f3ed85, 3:db2b988d-215d-57ec-bede-2f464494b832, 4:7bf3f492-a474-5abe-88ac-7194105f1099, 5:a69b781c-faf2-5e17-9bff-942dd6d58e1e, 6:90ec41b7-0670-58dd-a553-9f752e79a3f0, 7:d91472a5-46be-5b6d-a55b-59468d69ba9b, 8:5acc91a0-5fd7-5021-86c0-a9d2e4ee124e, 9:399b3a78-0f97-5021-ac15-5bb388f8260e, 10:3bd7d82b-756f-5cda-944d-94c5df2cb8c9
Failures: labeled_relevant_chunks_missing_at_10

### VUE006 / dense_rerank_offline

watch(obj.count, ...) 一直没按预期触发，我只想盯着 count，不想监控整个对象，该怎么改？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 1.0, "hit_rate@3": 1.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 0.5, "ndcg@10": 0.6934264036172708}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.871099988231435, "dense_search": 0.43120002374053, "cross_encoder_rerank": 6332.3876000067685}
Top10: 1:90ec41b7-0670-58dd-a553-9f752e79a3f0, 2:a69b781c-faf2-5e17-9bff-942dd6d58e1e, 3:6df6403f-8dea-58e9-bd6a-514c4cdf368e, 4:0cdb0dde-c1b3-5414-9864-a45588c5076a, 5:97333d3a-4c97-5ddf-b170-a0aea786c63d, 6:e2800ff6-c50c-5f52-99b7-831b1347f720, 7:5d99a249-971f-57f8-a301-d07709e7901e, 8:e788e5c1-ee63-5e5b-a656-42f846f3ed85, 9:90bda472-1d76-59a5-9be1-f3b3765b6d0b, 10:d91472a5-46be-5b6d-a55b-59468d69ba9b
Failures: none

### VUE007 / dense_exact_offline

reactive 数组里放了 ref，取出来怎么还是个对象？我以为 Vue 都会帮忙拆开。

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.0, "hit_rate@5": 0.0, "recall@10": 0.3333333333333333, "hit_rate@10": 1.0, "mrr@10": 0.1, "ndcg@10": 0.13565197343244778}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 0.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.296199994627386, "dense_search": 0.6885000038892031, "cross_encoder_rerank": 0.0}
Top10: 1:49c99c25-2bc8-5160-b8db-4d67c728b3c7, 2:303a5d7e-3e46-5e10-ac60-549693aa26c3, 3:da2603d2-7929-5ce3-9217-cd86ad3f2955, 4:f2dc5afd-1de3-5074-bac7-ba2e9febd667, 5:0b66ff22-ff23-5b2c-917b-e1751095505a, 6:da91b8dd-87b7-56c9-b189-d662360d8d3d, 7:1bbe5952-a953-5a71-8973-d627be6ae29d, 8:6426ad40-dfce-56a0-a538-b258af5ca11e, 9:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 10:0acddac2-51f2-57d9-aa94-d7c60909bccf
Failures: labeled_relevant_chunks_missing_at_10

### VUE007 / dense_rerank_offline

reactive 数组里放了 ref，取出来怎么还是个对象？我以为 Vue 都会帮忙拆开。

Metrics: {"recall@1": 0.3333333333333333, "hit_rate@1": 1.0, "recall@3": 0.3333333333333333, "hit_rate@3": 1.0, "recall@5": 0.3333333333333333, "hit_rate@5": 1.0, "recall@10": 0.3333333333333333, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.46927872602275644}
Evidence groups: {"evidence_group_coverage@1": 1.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.296199994627386, "dense_search": 0.6885000038892031, "cross_encoder_rerank": 6461.604500014801}
Top10: 1:0acddac2-51f2-57d9-aa94-d7c60909bccf, 2:9aa8fcfa-59b2-5dd1-9ca9-200ba8c070a4, 3:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 4:4f39a83a-2200-5b6d-ac29-cbf29f3495f7, 5:9e7b4f5a-68a8-5d51-ad27-6ce534c99190, 6:f2dc5afd-1de3-5074-bac7-ba2e9febd667, 7:0b66ff22-ff23-5b2c-917b-e1751095505a, 8:303a5d7e-3e46-5e10-ac60-549693aa26c3, 9:7a9e2078-d610-5ca9-9c0d-824bd581d161, 10:1c6906ee-9f65-5463-8a09-0c1e1f83e9d9
Failures: labeled_relevant_chunks_missing_at_10

### VUE008 / dense_exact_offline

页面外层和内层都 provide 了同名配置，最里面的组件 inject 到底会用哪一份？

Metrics: {"recall@1": 0.3333333333333333, "hit_rate@1": 1.0, "recall@3": 0.6666666666666666, "hit_rate@3": 1.0, "recall@5": 0.6666666666666666, "hit_rate@5": 1.0, "recall@10": 0.6666666666666666, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.7039180890341347}
Evidence groups: {"evidence_group_coverage@1": 1.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.03180000022985, "dense_search": 0.49940001918002963, "cross_encoder_rerank": 0.0}
Top10: 1:9e7b4f5a-68a8-5d51-ad27-6ce534c99190, 2:605afb9c-8be4-53af-9939-9820a44bd636, 3:f7de642c-8c51-5935-b29d-e813ff85d667, 4:51c8b1a3-8503-51f0-83a3-06c32e7cd952, 5:39306021-aad3-5ab4-b8ef-2089274e1c23, 6:c4563aa4-69c4-55ae-9491-5f0c41a29890, 7:8063841a-91e4-5885-8676-c74256919d55, 8:200bc2fe-48a3-54d5-9e06-9ba7aab09a90, 9:da91b8dd-87b7-56c9-b189-d662360d8d3d, 10:bf9cd212-476d-5496-8800-b97f88ca327c
Failures: labeled_relevant_chunks_missing_at_10

### VUE008 / dense_rerank_offline

页面外层和内层都 provide 了同名配置，最里面的组件 inject 到底会用哪一份？

Metrics: {"recall@1": 0.3333333333333333, "hit_rate@1": 1.0, "recall@3": 0.3333333333333333, "hit_rate@3": 1.0, "recall@5": 0.6666666666666666, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.8385465274895063}
Evidence groups: {"evidence_group_coverage@1": 1.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.03180000022985, "dense_search": 0.49940001918002963, "cross_encoder_rerank": 6311.206900019897}
Top10: 1:f7de642c-8c51-5935-b29d-e813ff85d667, 2:605afb9c-8be4-53af-9939-9820a44bd636, 3:51c8b1a3-8503-51f0-83a3-06c32e7cd952, 4:9e7b4f5a-68a8-5d51-ad27-6ce534c99190, 5:41cf975d-bcd2-5741-b791-398c3cf38ef1, 6:6c6a0da9-16b7-505e-a86f-e4c448a3a84f, 7:7f649526-c6cf-565e-841d-220c9ddb819f, 8:200bc2fe-48a3-54d5-9e06-9ba7aab09a90, 9:debd32fb-5056-5d62-b3ce-95cb50883277, 10:50476fce-cc56-5fb7-85b8-c4b220f7cc0c
Failures: none

### VUE009 / dense_exact_offline

父组件已经拿到子组件 ref 了，为什么调用不到 script setup 里写的那个方法？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.0, "hit_rate@5": 0.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 0.16666666666666666, "ndcg@10": 0.39564672360221187}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 0.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.000600013881922, "dense_search": 0.45780002255924046, "cross_encoder_rerank": 0.0}
Top10: 1:6c6a0da9-16b7-505e-a86f-e4c448a3a84f, 2:9e7b4f5a-68a8-5d51-ad27-6ce534c99190, 3:af17e069-2291-5e66-ab9e-3e461f361655, 4:49c99c25-2bc8-5160-b8db-4d67c728b3c7, 5:7ad21482-7a99-5298-b491-e4c038d091ed, 6:39306021-aad3-5ab4-b8ef-2089274e1c23, 7:94c5c015-934e-56ce-bf8f-b2e48d2f1227, 8:a37087d2-101e-5332-8eb4-8ad4f81c8caf, 9:303a5d7e-3e46-5e10-ac60-549693aa26c3, 10:a4c45296-6467-56cf-abc4-1ab6df219fe9
Failures: none

### VUE009 / dense_rerank_offline

父组件已经拿到子组件 ref 了，为什么调用不到 script setup 里写的那个方法？

Metrics: {"recall@1": 0.5, "hit_rate@1": 1.0, "recall@3": 0.5, "hit_rate@3": 1.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.8315546295836225}
Evidence groups: {"evidence_group_coverage@1": 0.5, "evidence_group_coverage@3": 0.5, "evidence_group_coverage@5": 0.5, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.000600013881922, "dense_search": 0.45780002255924046, "cross_encoder_rerank": 6358.9920999947935}
Top10: 1:a4c45296-6467-56cf-abc4-1ab6df219fe9, 2:bf9cd212-476d-5496-8800-b97f88ca327c, 3:f77c7aa6-62a8-5287-97ca-f2251684cf0c, 4:6c6a0da9-16b7-505e-a86f-e4c448a3a84f, 5:0f8e1a48-a80a-5e02-8265-590e6dee4d02, 6:39306021-aad3-5ab4-b8ef-2089274e1c23, 7:bd25d6f5-da4c-58c1-8947-f810071a1b1b, 8:9e7b4f5a-68a8-5d51-ad27-6ce534c99190, 9:7ad21482-7a99-5298-b491-e4c038d091ed, 10:8f0a5fb6-3b42-52cb-b0a0-91ce2e5ae0f5
Failures: none

### VUE010 / dense_exact_offline

我把 useXXX 返回的状态解构出来用，页面就不更新了。组合式函数应该返回什么结构才不容易踩这个坑？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.0, "hit_rate@5": 0.0, "recall@10": 0.5, "hit_rate@10": 1.0, "mrr@10": 0.125, "ndcg@10": 0.19342640361727081}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 0.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.49699998111464, "dense_search": 0.5882999976165593, "cross_encoder_rerank": 0.0}
Top10: 1:714936ce-6406-554d-b973-2a203298dc6f, 2:7a9e2078-d610-5ca9-9c0d-824bd581d161, 3:312f7e93-4108-55d5-b002-f76890c5bb39, 4:d763c97a-26f7-5ec7-b43f-22d54ee9e9b5, 5:9727377d-866a-536a-87cf-8b81720723dc, 6:6c0a6720-fef6-59b2-a3bd-9ff0b257d0dc, 7:0c637b1f-991e-5d17-9162-91456a434925, 8:78622d60-8947-503b-afda-dd4ff065daf0, 9:2fec68ae-f214-59b6-95e5-37d905d03449, 10:c7b47ae6-8420-5a95-bc01-6da459d19e30
Failures: labeled_relevant_chunks_missing_at_10

### VUE010 / dense_rerank_offline

我把 useXXX 返回的状态解构出来用，页面就不更新了。组合式函数应该返回什么结构才不容易踩这个坑？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.5, "hit_rate@3": 1.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 0.3333333333333333, "ndcg@10": 0.5}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.5, "evidence_group_coverage@5": 0.5, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.49699998111464, "dense_search": 0.5882999976165593, "cross_encoder_rerank": 6457.988699985435}
Top10: 1:9727377d-866a-536a-87cf-8b81720723dc, 2:0c637b1f-991e-5d17-9162-91456a434925, 3:912be6b3-bf0c-52fa-b084-b32a071bda9b, 4:312f7e93-4108-55d5-b002-f76890c5bb39, 5:7a9e2078-d610-5ca9-9c0d-824bd581d161, 6:561a7a7f-2706-515d-8bf4-d615031cbbdd, 7:714936ce-6406-554d-b973-2a203298dc6f, 8:78622d60-8947-503b-afda-dd4ff065daf0, 9:6c0a6720-fef6-59b2-a3bd-9ff0b257d0dc, 10:d763c97a-26f7-5ec7-b43f-22d54ee9e9b5
Failures: none

### VUE011 / dense_exact_offline

搜索条件变化后要刷新接口数据，结果再拿来算一段展示文字。这两步都塞进 computed 合适吗，应该怎样分工？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.0, "hit_rate@5": 0.0, "recall@10": 0.0, "hit_rate@10": 0.0, "mrr@10": 0.0, "ndcg@10": 0.0}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 0.0, "evidence_group_coverage@10": 0.0}
Stage ms: {"query_embedding": 10.7475999975577, "dense_search": 0.5123000009916723, "cross_encoder_rerank": 0.0}
Top10: 1:1bbe5952-a953-5a71-8973-d627be6ae29d, 2:04e62ff7-622e-511a-98db-d16f055bb65c, 3:17cdc303-ca28-5f1a-8645-f00e1fd9a1ee, 4:a1aa067e-f86c-53f5-89c6-f2954ca8a399, 5:32d1acec-c589-57b1-bc98-9e162f558651, 6:f77c7aa6-62a8-5287-97ca-f2251684cf0c, 7:7f649526-c6cf-565e-841d-220c9ddb819f, 8:bd25d6f5-da4c-58c1-8947-f810071a1b1b, 9:2d08642f-76d2-5a41-a9c5-c127c49d0b76, 10:bf02ccc6-915f-583e-9f67-fcbf7f74af46
Failures: labeled_relevant_chunks_missing_at_10, necessary_evidence_groups_uncovered_at_10

### VUE011 / dense_rerank_offline

搜索条件变化后要刷新接口数据，结果再拿来算一段展示文字。这两步都塞进 computed 合适吗，应该怎样分工？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.0, "hit_rate@5": 0.0, "recall@10": 0.0, "hit_rate@10": 0.0, "mrr@10": 0.0, "ndcg@10": 0.0}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 0.0, "evidence_group_coverage@10": 0.0}
Stage ms: {"query_embedding": 10.7475999975577, "dense_search": 0.5123000009916723, "cross_encoder_rerank": 6296.624600014184}
Top10: 1:17cdc303-ca28-5f1a-8645-f00e1fd9a1ee, 2:e7a3fae7-1aef-535c-b29e-a3b5a619b3bd, 3:21be7e89-4a62-56d5-99f4-0b1c65699a3c, 4:40721f2d-40fb-52d5-b40d-18c6f96a5f78, 5:561a7a7f-2706-515d-8bf4-d615031cbbdd, 6:9ee183fd-fa2b-5d23-a3f6-63d3abfbf80c, 7:7f649526-c6cf-565e-841d-220c9ddb819f, 8:675b751e-f782-5245-a31c-7c8747b4bc51, 9:354a4c46-377b-582a-8706-bcb39fcdd5ee, 10:2b5b6baf-ae41-5459-b831-4809597c7b4b
Failures: labeled_relevant_chunks_missing_at_10, necessary_evidence_groups_uncovered_at_10

### VUE012 / dense_exact_offline

父组件把一个普通的可变 user 对象作为 prop 传给编辑器。子组件直接执行 props.user.name = '新名字'，和执行 props.user = 新对象有什么区别？推荐怎样把姓名修改交给父组件处理？

Metrics: {"recall@1": 0.14285714285714285, "hit_rate@1": 1.0, "recall@3": 0.2857142857142857, "hit_rate@3": 1.0, "recall@5": 0.2857142857142857, "hit_rate@5": 1.0, "recall@10": 0.2857142857142857, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.4123144993714363}
Evidence groups: {"evidence_group_coverage@1": 1.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 12.551599997095764, "dense_search": 0.34690002212300897, "cross_encoder_rerank": 0.0}
Top10: 1:cb0c49b4-fe85-52e6-8e8b-e126933a0c77, 2:17cdc303-ca28-5f1a-8645-f00e1fd9a1ee, 3:1e51ef13-4dab-5e04-a08e-7b5624fb54b3, 4:e9ce390e-aad9-5dca-8200-95aac529d753, 5:f2bd7a0f-4536-507e-a4fa-e87413716121, 6:c02ffcac-c99b-518c-a4fe-f872f64b184c, 7:bf9cd212-476d-5496-8800-b97f88ca327c, 8:3769516e-964b-55cd-ad0e-2035bcfdef73, 9:0f8e1a48-a80a-5e02-8265-590e6dee4d02, 10:79a575c6-fe67-54af-89e0-a06d44a22e52
Failures: labeled_relevant_chunks_missing_at_10

### VUE012 / dense_rerank_offline

父组件把一个普通的可变 user 对象作为 prop 传给编辑器。子组件直接执行 props.user.name = '新名字'，和执行 props.user = 新对象有什么区别？推荐怎样把姓名修改交给父组件处理？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.14285714285714285, "hit_rate@3": 1.0, "recall@5": 0.2857142857142857, "hit_rate@5": 1.0, "recall@10": 0.42857142857142855, "hit_rate@10": 1.0, "mrr@10": 0.3333333333333333, "ndcg@10": 0.32323192692014274}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.3333333333333333, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 12.551599997095764, "dense_search": 0.34690002212300897, "cross_encoder_rerank": 6339.125900005456}
Top10: 1:f77c7aa6-62a8-5287-97ca-f2251684cf0c, 2:17cdc303-ca28-5f1a-8645-f00e1fd9a1ee, 3:1e51ef13-4dab-5e04-a08e-7b5624fb54b3, 4:e9ce390e-aad9-5dca-8200-95aac529d753, 5:cb0c49b4-fe85-52e6-8e8b-e126933a0c77, 6:f7de642c-8c51-5935-b29d-e813ff85d667, 7:0f8e1a48-a80a-5e02-8265-590e6dee4d02, 8:bf9cd212-476d-5496-8800-b97f88ca327c, 9:354a4c46-377b-582a-8706-bcb39fcdd5ee, 10:8f0a5fb6-3b42-52cb-b0a0-91ce2e5ae0f5
Failures: labeled_relevant_chunks_missing_at_10, rerank_worsened_vs_dense

### VUE013 / dense_exact_offline

封装按钮时把 click 写进 emits，父组件的 @click 还是不是透传到原生按钮？为什么声明事件会影响这个行为？

Metrics: {"recall@1": 0.2, "hit_rate@1": 1.0, "recall@3": 0.4, "hit_rate@3": 1.0, "recall@5": 0.6, "hit_rate@5": 1.0, "recall@10": 0.8, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.7864489426433972}
Evidence groups: {"evidence_group_coverage@1": 0.5, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.093900007428601, "dense_search": 0.5003999976906925, "cross_encoder_rerank": 0.0}
Top10: 1:14715e3f-b60c-5d9b-91d8-18b640139142, 2:3b0f0264-6b3a-5091-9c44-ba77aa88f80b, 3:8ac182f3-5001-5e2e-be32-96cff001c95c, 4:8f0a5fb6-3b42-52cb-b0a0-91ce2e5ae0f5, 5:e7e2ac01-9973-5bf5-8b09-ca6066bc3f9a, 6:c312fa6b-944d-5ab9-8ca4-fad72d12422c, 7:50476fce-cc56-5fb7-85b8-c4b220f7cc0c, 8:90bda472-1d76-59a5-9be1-f3b3765b6d0b, 9:24112c6d-aa7e-5f69-9bdc-2127f4042050, 10:8fec4a85-79b0-509b-bd2c-72500dcd0bfc
Failures: labeled_relevant_chunks_missing_at_10

### VUE013 / dense_rerank_offline

封装按钮时把 click 写进 emits，父组件的 @click 还是不是透传到原生按钮？为什么声明事件会影响这个行为？

Metrics: {"recall@1": 0.2, "hit_rate@1": 1.0, "recall@3": 0.4, "hit_rate@3": 1.0, "recall@5": 0.4, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.844702407490702}
Evidence groups: {"evidence_group_coverage@1": 0.5, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.093900007428601, "dense_search": 0.5003999976906925, "cross_encoder_rerank": 6408.191499998793}
Top10: 1:14715e3f-b60c-5d9b-91d8-18b640139142, 2:8f0a5fb6-3b42-52cb-b0a0-91ce2e5ae0f5, 3:3b0f0264-6b3a-5091-9c44-ba77aa88f80b, 4:7ad21482-7a99-5298-b491-e4c038d091ed, 5:90bda472-1d76-59a5-9be1-f3b3765b6d0b, 6:24112c6d-aa7e-5f69-9bdc-2127f4042050, 7:560d6037-50db-51fc-a466-5bb2b407b0e5, 8:8ac182f3-5001-5e2e-be32-96cff001c95c, 9:e7e2ac01-9973-5bf5-8b09-ca6066bc3f9a, 10:8fec4a85-79b0-509b-bd2c-72500dcd0bfc
Failures: none

### VUE014 / dense_exact_offline

我想在 useFocus 中，等组件挂载后通过模板 ref 聚焦 input，并手动给 window 注册一个事件监听器。模板 ref 初始为空应该怎样处理？组件卸载时，手动注册的监听器应该在哪里移除？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.2, "hit_rate@3": 1.0, "recall@5": 0.2, "hit_rate@5": 1.0, "recall@10": 0.4, "hit_rate@10": 1.0, "mrr@10": 0.5, "ndcg@10": 0.31608365985743925}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.3333333333333333, "evidence_group_coverage@5": 0.3333333333333333, "evidence_group_coverage@10": 0.3333333333333333}
Stage ms: {"query_embedding": 12.015100015560165, "dense_search": 0.43810001807287335, "cross_encoder_rerank": 0.0}
Top10: 1:49c99c25-2bc8-5160-b8db-4d67c728b3c7, 2:bd25d6f5-da4c-58c1-8947-f810071a1b1b, 3:d7a5f209-8d1f-5b7d-8359-58c349c76e59, 4:39306021-aad3-5ab4-b8ef-2089274e1c23, 5:da91b8dd-87b7-56c9-b189-d662360d8d3d, 6:90bda472-1d76-59a5-9be1-f3b3765b6d0b, 7:7a9e2078-d610-5ca9-9c0d-824bd581d161, 8:14715e3f-b60c-5d9b-91d8-18b640139142, 9:bf02ccc6-915f-583e-9f67-fcbf7f74af46, 10:e788e5c1-ee63-5e5b-a656-42f846f3ed85
Failures: labeled_relevant_chunks_missing_at_10, necessary_evidence_groups_uncovered_at_10

### VUE014 / dense_rerank_offline

我想在 useFocus 中，等组件挂载后通过模板 ref 聚焦 input，并手动给 window 注册一个事件监听器。模板 ref 初始为空应该怎样处理？组件卸载时，手动注册的监听器应该在哪里移除？

Metrics: {"recall@1": 0.2, "hit_rate@1": 1.0, "recall@3": 0.4, "hit_rate@3": 1.0, "recall@5": 0.6, "hit_rate@5": 1.0, "recall@10": 0.6, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.6843515475204855}
Evidence groups: {"evidence_group_coverage@1": 0.3333333333333333, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 12.015100015560165, "dense_search": 0.43810001807287335, "cross_encoder_rerank": 6425.397099985275}
Top10: 1:bf02ccc6-915f-583e-9f67-fcbf7f74af46, 2:912be6b3-bf0c-52fa-b084-b32a071bda9b, 3:49c99c25-2bc8-5160-b8db-4d67c728b3c7, 4:4f39a83a-2200-5b6d-ac29-cbf29f3495f7, 5:bd25d6f5-da4c-58c1-8947-f810071a1b1b, 6:d7a5f209-8d1f-5b7d-8359-58c349c76e59, 7:39306021-aad3-5ab4-b8ef-2089274e1c23, 8:c312fa6b-944d-5ab9-8ca4-fad72d12422c, 9:90bda472-1d76-59a5-9be1-f3b3765b6d0b, 10:14715e3f-b60c-5d9b-91d8-18b640139142
Failures: labeled_relevant_chunks_missing_at_10

### VUE015 / dense_exact_offline

把 reactive 对象里的一个数字解构到局部变量，和从组合式函数拿到一个 ref 再解构，为什么更新效果不一样？

Metrics: {"recall@1": 0.25, "hit_rate@1": 1.0, "recall@3": 0.25, "hit_rate@3": 1.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 0.75, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.6804558477306826}
Evidence groups: {"evidence_group_coverage@1": 0.5, "evidence_group_coverage@3": 0.5, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.859799989499152, "dense_search": 0.5018999800086021, "cross_encoder_rerank": 0.0}
Top10: 1:4dbf7985-2e57-5fd4-be7d-efe56d8b62ed, 2:0acddac2-51f2-57d9-aa94-d7c60909bccf, 3:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 4:303a5d7e-3e46-5e10-ac60-549693aa26c3, 5:912be6b3-bf0c-52fa-b084-b32a071bda9b, 6:a2425d5f-5163-58d8-8d74-37d38abc304f, 7:1bbe5952-a953-5a71-8973-d627be6ae29d, 8:977439cd-9241-51b9-90c3-09309303fd09, 9:2fec68ae-f214-59b6-95e5-37d905d03449, 10:bf9cd212-476d-5496-8800-b97f88ca327c
Failures: labeled_relevant_chunks_missing_at_10

### VUE015 / dense_rerank_offline

把 reactive 对象里的一个数字解构到局部变量，和从组合式函数拿到一个 ref 再解构，为什么更新效果不一样？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.25, "hit_rate@3": 1.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 0.5, "hit_rate@10": 1.0, "mrr@10": 0.5, "ndcg@10": 0.4144299250118475}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.5, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.859799989499152, "dense_search": 0.5018999800086021, "cross_encoder_rerank": 6455.5846999865025}
Top10: 1:303a5d7e-3e46-5e10-ac60-549693aa26c3, 2:912be6b3-bf0c-52fa-b084-b32a071bda9b, 3:6c0a6720-fef6-59b2-a3bd-9ff0b257d0dc, 4:4dbf7985-2e57-5fd4-be7d-efe56d8b62ed, 5:4f39a83a-2200-5b6d-ac29-cbf29f3495f7, 6:7a9e2078-d610-5ca9-9c0d-824bd581d161, 7:312f7e93-4108-55d5-b002-f76890c5bb39, 8:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 9:3056d53e-be45-5cf7-92fe-4e81c399cb4a, 10:2fec68ae-f214-59b6-95e5-37d905d03449
Failures: labeled_relevant_chunks_missing_at_10, rerank_worsened_vs_dense

### VUE016 / dense_exact_offline

watch 和 watchEffect 是不是只差一个不用写监听源？如果回调里有 await，依赖追踪有什么容易漏掉的地方？

Metrics: {"recall@1": 0.5, "hit_rate@1": 1.0, "recall@3": 1.0, "hit_rate@3": 1.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 1.0}
Evidence groups: {"evidence_group_coverage@1": 0.6666666666666666, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 11.036700016120449, "dense_search": 0.47099997755140066, "cross_encoder_rerank": 0.0}
Top10: 1:eb733fbd-8a4c-595e-bebe-6f8c374b6aca, 2:e6a99cf2-692a-571b-bba4-cc7b833242b0, 3:e788e5c1-ee63-5e5b-a656-42f846f3ed85, 4:012e62d9-670e-50bc-aa7a-496b7c29ceff, 5:a69b781c-faf2-5e17-9bff-942dd6d58e1e, 6:b7b4b10e-3228-5438-9b74-94acea8e14c9, 7:cb8f0eda-ad24-5450-936d-a2eef1905f3b, 8:7bf3f492-a474-5abe-88ac-7194105f1099, 9:fd72e98f-d467-5581-9e1b-8e9d70b55fed, 10:d91472a5-46be-5b6d-a55b-59468d69ba9b
Failures: none

### VUE016 / dense_rerank_offline

watch 和 watchEffect 是不是只差一个不用写监听源？如果回调里有 await，依赖追踪有什么容易漏掉的地方？

Metrics: {"recall@1": 0.5, "hit_rate@1": 1.0, "recall@3": 1.0, "hit_rate@3": 1.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 1.0}
Evidence groups: {"evidence_group_coverage@1": 0.3333333333333333, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 11.036700016120449, "dense_search": 0.47099997755140066, "cross_encoder_rerank": 6394.333100004587}
Top10: 1:e6a99cf2-692a-571b-bba4-cc7b833242b0, 2:eb733fbd-8a4c-595e-bebe-6f8c374b6aca, 3:6df6403f-8dea-58e9-bd6a-514c4cdf368e, 4:93ee0ba2-4f0f-5338-b6c6-b02f9b42f907, 5:0cdb0dde-c1b3-5414-9864-a45588c5076a, 6:b7b4b10e-3228-5438-9b74-94acea8e14c9, 7:5d99a249-971f-57f8-a301-d07709e7901e, 8:012e62d9-670e-50bc-aa7a-496b7c29ceff, 9:e788e5c1-ee63-5e5b-a656-42f846f3ed85, 10:d91472a5-46be-5b6d-a55b-59468d69ba9b
Failures: none

### VUE017 / dense_exact_offline

同一个 ref 放进 reactive 对象属性时不用 .value，放进数组或 Map 就要写，这两种情况到底怎么区分？

Metrics: {"recall@1": 0.2, "hit_rate@1": 1.0, "recall@3": 0.2, "hit_rate@3": 1.0, "recall@5": 0.2, "hit_rate@5": 1.0, "recall@10": 0.8, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.6650039261717311}
Evidence groups: {"evidence_group_coverage@1": 1.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.816200006753206, "dense_search": 0.4592000041157007, "cross_encoder_rerank": 0.0}
Top10: 1:0acddac2-51f2-57d9-aa94-d7c60909bccf, 2:303a5d7e-3e46-5e10-ac60-549693aa26c3, 3:da2603d2-7929-5ce3-9217-cd86ad3f2955, 4:49c99c25-2bc8-5160-b8db-4d67c728b3c7, 5:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 6:81f8da2e-7ef3-530a-8195-12de98776e89, 7:a2425d5f-5163-58d8-8d74-37d38abc304f, 8:4dbf7985-2e57-5fd4-be7d-efe56d8b62ed, 9:6e72d545-de1b-5695-9831-10fcdb824335, 10:a53426c4-b3fd-5e34-bbd0-6a6c5c21450c
Failures: labeled_relevant_chunks_missing_at_10

### VUE017 / dense_rerank_offline

同一个 ref 放进 reactive 对象属性时不用 .value，放进数组或 Map 就要写，这两种情况到底怎么区分？

Metrics: {"recall@1": 0.2, "hit_rate@1": 1.0, "recall@3": 0.6, "hit_rate@3": 1.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 1.0}
Evidence groups: {"evidence_group_coverage@1": 0.6666666666666666, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.816200006753206, "dense_search": 0.4592000041157007, "cross_encoder_rerank": 6444.86690001213}
Top10: 1:a53426c4-b3fd-5e34-bbd0-6a6c5c21450c, 2:81f8da2e-7ef3-530a-8195-12de98776e89, 3:2fec68ae-f214-59b6-95e5-37d905d03449, 4:0acddac2-51f2-57d9-aa94-d7c60909bccf, 5:4dbf7985-2e57-5fd4-be7d-efe56d8b62ed, 6:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 7:e70277a8-7ed1-561c-9138-1582fdf499af, 8:f2dc5afd-1de3-5074-bac7-ba2e9febd667, 9:a2425d5f-5163-58d8-8d74-37d38abc304f, 10:409e0a1a-383a-550e-9239-f0c313cb90c6
Failures: none

### VUE018 / dense_exact_offline

插槽写在父组件里，为什么不能直接读子组件的局部变量？作用域插槽是怎么把这部分数据交给我的？

Metrics: {"recall@1": 0.25, "hit_rate@1": 1.0, "recall@3": 0.75, "hit_rate@3": 1.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.9828920819566879}
Evidence groups: {"evidence_group_coverage@1": 0.5, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.52819998585619, "dense_search": 0.5261999904178083, "cross_encoder_rerank": 0.0}
Top10: 1:94c5c015-934e-56ce-bf8f-b2e48d2f1227, 2:6c17ff85-749b-5089-aba8-32381c08392c, 3:675b751e-f782-5245-a31c-7c8747b4bc51, 4:d4828158-3ac3-5f58-ba81-03ebec690f06, 5:444f4b72-184b-5ad3-a962-27ad89bec941, 6:a5eae0d5-868a-5ff4-afa5-a49efbea2862, 7:2d08642f-76d2-5a41-a9c5-c127c49d0b76, 8:a37087d2-101e-5332-8eb4-8ad4f81c8caf, 9:7ad21482-7a99-5298-b491-e4c038d091ed, 10:32d1acec-c589-57b1-bc98-9e162f558651
Failures: none

### VUE018 / dense_rerank_offline

插槽写在父组件里，为什么不能直接读子组件的局部变量？作用域插槽是怎么把这部分数据交给我的？

Metrics: {"recall@1": 0.25, "hit_rate@1": 1.0, "recall@3": 0.75, "hit_rate@3": 1.0, "recall@5": 0.75, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.9619991470595832}
Evidence groups: {"evidence_group_coverage@1": 0.5, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 10.52819998585619, "dense_search": 0.5261999904178083, "cross_encoder_rerank": 6318.25359998038}
Top10: 1:6c17ff85-749b-5089-aba8-32381c08392c, 2:675b751e-f782-5245-a31c-7c8747b4bc51, 3:94c5c015-934e-56ce-bf8f-b2e48d2f1227, 4:7ad21482-7a99-5298-b491-e4c038d091ed, 5:41d181fa-3b4a-5220-ad1e-9dc62578993b, 6:bbe82e73-5859-5184-8e83-0f1bffd843e0, 7:444f4b72-184b-5ad3-a962-27ad89bec941, 8:1d0a7796-6242-5380-ade8-e49b517cbc22, 9:2d08642f-76d2-5a41-a9c5-c127c49d0b76, 10:a5eae0d5-868a-5ff4-afa5-a49efbea2862
Failures: rerank_worsened_vs_dense

### VUE019 / dense_exact_offline

把对象交给 reactive 后，返回值和原对象用 === 比较为什么不相等？修改时应该一直用哪一个？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.25, "hit_rate@3": 1.0, "recall@5": 0.25, "hit_rate@5": 1.0, "recall@10": 0.5, "hit_rate@10": 1.0, "mrr@10": 0.3333333333333333, "ndcg@10": 0.3080351663449861}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.47629997972399, "dense_search": 0.3620999923441559, "cross_encoder_rerank": 0.0}
Top10: 1:409e0a1a-383a-550e-9239-f0c313cb90c6, 2:912be6b3-bf0c-52fa-b084-b32a071bda9b, 3:1c6906ee-9f65-5463-8a09-0c1e1f83e9d9, 4:a53426c4-b3fd-5e34-bbd0-6a6c5c21450c, 5:720f300d-f184-5069-9ad2-3aafb122b8cc, 6:714936ce-6406-554d-b973-2a203298dc6f, 7:17cdc303-ca28-5f1a-8645-f00e1fd9a1ee, 8:cfb3ff2a-4f17-5b20-ac88-58a49a34e68c, 9:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 10:a2425d5f-5163-58d8-8d74-37d38abc304f
Failures: labeled_relevant_chunks_missing_at_10

### VUE019 / dense_rerank_offline

把对象交给 reactive 后，返回值和原对象用 === 比较为什么不相等？修改时应该一直用哪一个？

Metrics: {"recall@1": 0.25, "hit_rate@1": 1.0, "recall@3": 0.5, "hit_rate@3": 1.0, "recall@5": 0.75, "hit_rate@5": 1.0, "recall@10": 0.75, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.75369761125927}
Evidence groups: {"evidence_group_coverage@1": 1.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.47629997972399, "dense_search": 0.3620999923441559, "cross_encoder_rerank": 6287.0603000046685}
Top10: 1:1c6906ee-9f65-5463-8a09-0c1e1f83e9d9, 2:409e0a1a-383a-550e-9239-f0c313cb90c6, 3:2fec68ae-f214-59b6-95e5-37d905d03449, 4:a2425d5f-5163-58d8-8d74-37d38abc304f, 5:78622d60-8947-503b-afda-dd4ff065daf0, 6:81f8da2e-7ef3-530a-8195-12de98776e89, 7:a53426c4-b3fd-5e34-bbd0-6a6c5c21450c, 8:714936ce-6406-554d-b973-2a203298dc6f, 9:720f300d-f184-5069-9ad2-3aafb122b8cc, 10:0acddac2-51f2-57d9-aa94-d7c60909bccf
Failures: labeled_relevant_chunks_missing_at_10

### VUE020 / dense_exact_offline

在自定义组件上使用不带参数的 v-model="value" 时，不用 defineModel 应该怎样实现？子组件接收哪个 prop、触发哪个事件？这和 v-model:title 有什么区别？

Metrics: {"recall@1": 0.16666666666666666, "hit_rate@1": 1.0, "recall@3": 0.3333333333333333, "hit_rate@3": 1.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 0.6666666666666666, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.7316362001126299}
Evidence groups: {"evidence_group_coverage@1": 0.6666666666666666, "evidence_group_coverage@3": 0.6666666666666666, "evidence_group_coverage@5": 0.6666666666666666, "evidence_group_coverage@10": 0.6666666666666666}
Stage ms: {"query_embedding": 12.80409999890253, "dense_search": 0.5278000026009977, "cross_encoder_rerank": 0.0}
Top10: 1:454bd082-74ca-5e75-81f2-c53217654372, 2:e7a3fae7-1aef-535c-b29e-a3b5a619b3bd, 3:9d04daae-e178-5864-b2ff-df6e93a9e83b, 4:bf9cd212-476d-5496-8800-b97f88ca327c, 5:79a575c6-fe67-54af-89e0-a06d44a22e52, 6:1bbe5952-a953-5a71-8973-d627be6ae29d, 7:bca521c9-b6d5-5f4a-90f6-d0717e5bd1be, 8:e9ce390e-aad9-5dca-8200-95aac529d753, 9:e7e2ac01-9973-5bf5-8b09-ca6066bc3f9a, 10:39306021-aad3-5ab4-b8ef-2089274e1c23
Failures: labeled_relevant_chunks_missing_at_10, necessary_evidence_groups_uncovered_at_10

### VUE020 / dense_rerank_offline

在自定义组件上使用不带参数的 v-model="value" 时，不用 defineModel 应该怎样实现？子组件接收哪个 prop、触发哪个事件？这和 v-model:title 有什么区别？

Metrics: {"recall@1": 0.16666666666666666, "hit_rate@1": 1.0, "recall@3": 0.3333333333333333, "hit_rate@3": 1.0, "recall@5": 0.6666666666666666, "hit_rate@5": 1.0, "recall@10": 0.8333333333333334, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.8417771098923535}
Evidence groups: {"evidence_group_coverage@1": 0.6666666666666666, "evidence_group_coverage@3": 0.6666666666666666, "evidence_group_coverage@5": 0.6666666666666666, "evidence_group_coverage@10": 0.6666666666666666}
Stage ms: {"query_embedding": 12.80409999890253, "dense_search": 0.5278000026009977, "cross_encoder_rerank": 6828.390999988187}
Top10: 1:454bd082-74ca-5e75-81f2-c53217654372, 2:e7a3fae7-1aef-535c-b29e-a3b5a619b3bd, 3:0f8e1a48-a80a-5e02-8265-590e6dee4d02, 4:bf9cd212-476d-5496-8800-b97f88ca327c, 5:507f1310-f227-5746-9b63-41dd014abf1c, 6:9d04daae-e178-5864-b2ff-df6e93a9e83b, 7:1bbe5952-a953-5a71-8973-d627be6ae29d, 8:75d2c58d-95cb-5704-8e6d-05bc63f0f515, 9:bca521c9-b6d5-5f4a-90f6-d0717e5bd1be, 10:3cefba0f-0104-5d34-9885-b417bf805279
Failures: labeled_relevant_chunks_missing_at_10, necessary_evidence_groups_uncovered_at_10

### VUE021 / dense_exact_offline

项目用 Vue Router 4，登录过期时 beforeEach 怎么配置才能登录后回到原来的地址？请给完整配置。

Metrics: {}
Evidence groups: {}
Stage ms: {"query_embedding": 13.574200012953952, "dense_search": 0.5688999954145402, "cross_encoder_rerank": 0.0}
Top10: 1:fd72e98f-d467-5581-9e1b-8e9d70b55fed, 2:cb8f0eda-ad24-5450-936d-a2eef1905f3b, 3:e2800ff6-c50c-5f52-99b7-831b1347f720, 4:7b6df58f-aded-5fa8-986d-6c7e5508e301, 5:93ee0ba2-4f0f-5338-b6c6-b02f9b42f907, 6:714936ce-6406-554d-b973-2a203298dc6f, 7:d0066f9c-9d06-598f-9e47-366d9ef1edd3, 8:3769516e-964b-55cd-ad0e-2035bcfdef73, 9:9b9c4f46-b134-59db-b70e-d22df5725d4a, 10:7bf3f492-a474-5abe-88ac-7194105f1099
Failures: negative_query_returned_results

### VUE021 / dense_rerank_offline

项目用 Vue Router 4，登录过期时 beforeEach 怎么配置才能登录后回到原来的地址？请给完整配置。

Metrics: {}
Evidence groups: {}
Stage ms: {"query_embedding": 13.574200012953952, "dense_search": 0.5688999954145402, "cross_encoder_rerank": 6678.858400002355}
Top10: 1:93ee0ba2-4f0f-5338-b6c6-b02f9b42f907, 2:7b6df58f-aded-5fa8-986d-6c7e5508e301, 3:714936ce-6406-554d-b973-2a203298dc6f, 4:3c4d3fe0-ef6c-5163-bbbe-e5de1f6adf2d, 5:cfb3ff2a-4f17-5b20-ac88-58a49a34e68c, 6:531c52e7-006a-57f4-97b8-e80f9b35e339, 7:1c6906ee-9f65-5463-8a09-0c1e1f83e9d9, 8:977439cd-9241-51b9-90c3-09309303fd09, 9:6c0a6720-fef6-59b2-a3bd-9ff0b257d0dc, 10:e7a3fae7-1aef-535c-b29e-a3b5a619b3bd
Failures: negative_query_returned_results

### VUE022 / dense_exact_offline

Pinia store 想跨标签页同步，还要让持久化缓存两小时后失效，具体插件配置怎么写？

Metrics: {}
Evidence groups: {}
Stage ms: {"query_embedding": 10.711400012951344, "dense_search": 0.5483000131789595, "cross_encoder_rerank": 0.0}
Top10: 1:7a9e2078-d610-5ca9-9c0d-824bd581d161, 2:2d08642f-76d2-5a41-a9c5-c127c49d0b76, 3:c39cf96d-d919-5521-9dc6-263320b3d1cd, 4:32d1acec-c589-57b1-bc98-9e162f558651, 5:3769516e-964b-55cd-ad0e-2035bcfdef73, 6:311e4473-3182-5dcf-82cd-9e855bf2c846, 7:bf02ccc6-915f-583e-9f67-fcbf7f74af46, 8:d0066f9c-9d06-598f-9e47-366d9ef1edd3, 9:bd25d6f5-da4c-58c1-8947-f810071a1b1b, 10:9aa8fcfa-59b2-5dd1-9ca9-200ba8c070a4
Failures: negative_query_returned_results

### VUE022 / dense_rerank_offline

Pinia store 想跨标签页同步，还要让持久化缓存两小时后失效，具体插件配置怎么写？

Metrics: {}
Evidence groups: {}
Stage ms: {"query_embedding": 10.711400012951344, "dense_search": 0.5483000131789595, "cross_encoder_rerank": 6505.855499999598}
Top10: 1:bbe82e73-5859-5184-8e83-0f1bffd843e0, 2:32d1acec-c589-57b1-bc98-9e162f558651, 3:41d181fa-3b4a-5220-ad1e-9dc62578993b, 4:04e62ff7-622e-511a-98db-d16f055bb65c, 5:2d08642f-76d2-5a41-a9c5-c127c49d0b76, 6:6c6a0da9-16b7-505e-a86f-e4c448a3a84f, 7:c39cf96d-d919-5521-9dc6-263320b3d1cd, 8:a4755e23-ddd2-5589-8d7c-47222e7be266, 9:1250cc7b-22e5-598e-a9ad-7aa5c4aa83f9, 10:444f4b72-184b-5ad3-a962-27ad89bec941
Failures: negative_query_returned_results

### VUE023 / dense_exact_offline

Vite 开发服务器把 /socket 代理到后端 WebSocket，vite.config.ts 里代理规则应该怎么写？

Metrics: {}
Evidence groups: {}
Stage ms: {"query_embedding": 10.391399991931394, "dense_search": 0.5053000058978796, "cross_encoder_rerank": 0.0}
Top10: 1:1c6906ee-9f65-5463-8a09-0c1e1f83e9d9, 2:c7b47ae6-8420-5a95-bc01-6da459d19e30, 3:977439cd-9241-51b9-90c3-09309303fd09, 4:7a9e2078-d610-5ca9-9c0d-824bd581d161, 5:605afb9c-8be4-53af-9939-9820a44bd636, 6:3769516e-964b-55cd-ad0e-2035bcfdef73, 7:354a4c46-377b-582a-8706-bcb39fcdd5ee, 8:c02ffcac-c99b-518c-a4fe-f872f64b184c, 9:62e663f6-fd0c-559c-83e0-7c188ac39bb9, 10:9f9ddf62-fdb3-5b6b-a137-5aaa5c4c707b
Failures: negative_query_returned_results

### VUE023 / dense_rerank_offline

Vite 开发服务器把 /socket 代理到后端 WebSocket，vite.config.ts 里代理规则应该怎么写？

Metrics: {}
Evidence groups: {}
Stage ms: {"query_embedding": 10.391399991931394, "dense_search": 0.5053000058978796, "cross_encoder_rerank": 5973.502399981953}
Top10: 1:409e0a1a-383a-550e-9239-f0c313cb90c6, 2:d8a46e30-910b-58c3-9164-8a458bbeb36d, 3:1c6906ee-9f65-5463-8a09-0c1e1f83e9d9, 4:9b9c4f46-b134-59db-b70e-d22df5725d4a, 5:7f649526-c6cf-565e-841d-220c9ddb819f, 6:200bc2fe-48a3-54d5-9e06-9ba7aab09a90, 7:977439cd-9241-51b9-90c3-09309303fd09, 8:9f9ddf62-fdb3-5b6b-a137-5aaa5c4c707b, 9:605afb9c-8be4-53af-9939-9820a44bd636, 10:354a4c46-377b-582a-8706-bcb39fcdd5ee
Failures: negative_query_returned_results

### VUE024 / dense_exact_offline

我的 UserProfile.vue 第 87 行报 Cannot read properties of undefined，你直接告诉我那一行该怎么改，代码暂时不能提供。

Metrics: {}
Evidence groups: {}
Stage ms: {"query_embedding": 12.833399989176542, "dense_search": 0.5067000165581703, "cross_encoder_rerank": 0.0}
Top10: 1:7b6df58f-aded-5fa8-986d-6c7e5508e301, 2:17cdc303-ca28-5f1a-8645-f00e1fd9a1ee, 3:4f39a83a-2200-5b6d-ac29-cbf29f3495f7, 4:62e663f6-fd0c-559c-83e0-7c188ac39bb9, 5:bd25d6f5-da4c-58c1-8947-f810071a1b1b, 6:9a542f68-9eb0-5969-ac62-1b5f90ee00ad, 7:354a4c46-377b-582a-8706-bcb39fcdd5ee, 8:2b5b6baf-ae41-5459-b831-4809597c7b4b, 9:9b9c4f46-b134-59db-b70e-d22df5725d4a, 10:40721f2d-40fb-52d5-b40d-18c6f96a5f78
Failures: negative_query_returned_results

### VUE024 / dense_rerank_offline

我的 UserProfile.vue 第 87 行报 Cannot read properties of undefined，你直接告诉我那一行该怎么改，代码暂时不能提供。

Metrics: {}
Evidence groups: {}
Stage ms: {"query_embedding": 12.833399989176542, "dense_search": 0.5067000165581703, "cross_encoder_rerank": 5984.412999998312}
Top10: 1:9b9c4f46-b134-59db-b70e-d22df5725d4a, 2:507f1310-f227-5746-9b63-41dd014abf1c, 3:40721f2d-40fb-52d5-b40d-18c6f96a5f78, 4:3769516e-964b-55cd-ad0e-2035bcfdef73, 5:f48000a8-6daa-514a-93e1-79db6cf4d511, 6:c39cf96d-d919-5521-9dc6-263320b3d1cd, 7:9a542f68-9eb0-5969-ac62-1b5f90ee00ad, 8:c312fa6b-944d-5ab9-8ca4-fad72d12422c, 9:200bc2fe-48a3-54d5-9e06-9ba7aab09a90, 10:9ee183fd-fa2b-5d23-a3f6-63d3abfbf80c
Failures: negative_query_returned_results

### VUE025 / dense_exact_offline

一万个带校验的输入框全部改成 ref 后，在我的电脑上每次更新能保证低于 16ms 吗？给我确定的耗时数值。

Metrics: {}
Evidence groups: {}
Stage ms: {"query_embedding": 11.678900016704574, "dense_search": 0.5428000004030764, "cross_encoder_rerank": 0.0}
Top10: 1:17cdc303-ca28-5f1a-8645-f00e1fd9a1ee, 2:cb0c49b4-fe85-52e6-8e8b-e126933a0c77, 3:b0cb3957-cb47-5a82-a831-9add7205c849, 4:9ee183fd-fa2b-5d23-a3f6-63d3abfbf80c, 5:bd25d6f5-da4c-58c1-8947-f810071a1b1b, 6:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 7:303a5d7e-3e46-5e10-ac60-549693aa26c3, 8:6c0a6720-fef6-59b2-a3bd-9ff0b257d0dc, 9:a53426c4-b3fd-5e34-bbd0-6a6c5c21450c, 10:1bbe5952-a953-5a71-8973-d627be6ae29d
Failures: negative_query_returned_results

### VUE025 / dense_rerank_offline

一万个带校验的输入框全部改成 ref 后，在我的电脑上每次更新能保证低于 16ms 吗？给我确定的耗时数值。

Metrics: {}
Evidence groups: {}
Stage ms: {"query_embedding": 11.678900016704574, "dense_search": 0.5428000004030764, "cross_encoder_rerank": 6296.8220000038855}
Top10: 1:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 2:f2dc5afd-1de3-5074-bac7-ba2e9febd667, 3:b0cb3957-cb47-5a82-a831-9add7205c849, 4:a53426c4-b3fd-5e34-bbd0-6a6c5c21450c, 5:1bbe5952-a953-5a71-8973-d627be6ae29d, 6:977439cd-9241-51b9-90c3-09309303fd09, 7:cb0c49b4-fe85-52e6-8e8b-e126933a0c77, 8:9aa8fcfa-59b2-5dd1-9ca9-200ba8c070a4, 9:189ce522-8216-5241-b358-34fc3863bef3, 10:da2603d2-7929-5ce3-9217-cd86ad3f2955
Failures: negative_query_returned_results

### VUE027 / dense_exact_offline

升级到 Vue 3.5 后，从 defineProps 解构出来的变量为什么又能跟着更新了？在 3.4 项目里也能这样理解吗？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.0, "hit_rate@5": 0.0, "recall@10": 0.0, "hit_rate@10": 0.0, "mrr@10": 0.0, "ndcg@10": 0.0}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 0.0, "evidence_group_coverage@10": 0.0}
Stage ms: {"query_embedding": 10.68529998883605, "dense_search": 0.4661999992094934, "cross_encoder_rerank": 0.0}
Top10: 1:977439cd-9241-51b9-90c3-09309303fd09, 2:cb0c49b4-fe85-52e6-8e8b-e126933a0c77, 3:c8f6bef7-5022-56d2-b24a-607ab394115d, 4:a61ced98-5f68-5f24-9fa9-0f0239cb5331, 5:1bbe5952-a953-5a71-8973-d627be6ae29d, 6:bdbc32a5-5f53-5bb3-892f-2ee0548f42ad, 7:9b9c4f46-b134-59db-b70e-d22df5725d4a, 8:17cdc303-ca28-5f1a-8645-f00e1fd9a1ee, 9:cb529efc-8e18-5ac6-bcc8-7ecae08520cd, 10:bf9cd212-476d-5496-8800-b97f88ca327c
Failures: labeled_relevant_chunks_missing_at_10, necessary_evidence_groups_uncovered_at_10

### VUE027 / dense_rerank_offline

升级到 Vue 3.5 后，从 defineProps 解构出来的变量为什么又能跟着更新了？在 3.4 项目里也能这样理解吗？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.0, "hit_rate@3": 0.0, "recall@5": 0.0, "hit_rate@5": 0.0, "recall@10": 0.0, "hit_rate@10": 0.0, "mrr@10": 0.0, "ndcg@10": 0.0}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 0.0, "evidence_group_coverage@5": 0.0, "evidence_group_coverage@10": 0.0}
Stage ms: {"query_embedding": 10.68529998883605, "dense_search": 0.4661999992094934, "cross_encoder_rerank": 6186.548600002425}
Top10: 1:bf9cd212-476d-5496-8800-b97f88ca327c, 2:79a575c6-fe67-54af-89e0-a06d44a22e52, 3:0f8e1a48-a80a-5e02-8265-590e6dee4d02, 4:531c52e7-006a-57f4-97b8-e80f9b35e339, 5:17cdc303-ca28-5f1a-8645-f00e1fd9a1ee, 6:1e51ef13-4dab-5e04-a08e-7b5624fb54b3, 7:23298043-752b-55c9-b05e-964933989819, 8:c8f6bef7-5022-56d2-b24a-607ab394115d, 9:e2800ff6-c50c-5f52-99b7-831b1347f720, 10:cb0c49b4-fe85-52e6-8e8b-e126933a0c77
Failures: labeled_relevant_chunks_missing_at_10, necessary_evidence_groups_uncovered_at_10

### VUE028 / dense_exact_offline

Vue 3.4 项目复制 useTemplateRef 示例后用不了，这个 API 从哪个版本开始有，旧项目应该怎样拿模板引用？

Metrics: {"recall@1": 0.5, "hit_rate@1": 1.0, "recall@3": 1.0, "hit_rate@3": 1.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 1.0}
Evidence groups: {"evidence_group_coverage@1": 1.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.569199988618493, "dense_search": 0.4504999960772693, "cross_encoder_rerank": 0.0}
Top10: 1:bf02ccc6-915f-583e-9f67-fcbf7f74af46, 2:da91b8dd-87b7-56c9-b189-d662360d8d3d, 3:f2dc5afd-1de3-5074-bac7-ba2e9febd667, 4:bd25d6f5-da4c-58c1-8947-f810071a1b1b, 5:da2603d2-7929-5ce3-9217-cd86ad3f2955, 6:c7b47ae6-8420-5a95-bc01-6da459d19e30, 7:6426ad40-dfce-56a0-a538-b258af5ca11e, 8:87131309-0cbf-5c9c-8f8a-cd6aa6e8643d, 9:7b6df58f-aded-5fa8-986d-6c7e5508e301, 10:531c52e7-006a-57f4-97b8-e80f9b35e339
Failures: none

### VUE028 / dense_rerank_offline

Vue 3.4 项目复制 useTemplateRef 示例后用不了，这个 API 从哪个版本开始有，旧项目应该怎样拿模板引用？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.5, "hit_rate@3": 1.0, "recall@5": 1.0, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 0.5, "ndcg@10": 0.6509209298071326}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 9.569199988618493, "dense_search": 0.4504999960772693, "cross_encoder_rerank": 6220.4255999822635}
Top10: 1:f2dc5afd-1de3-5074-bac7-ba2e9febd667, 2:bf02ccc6-915f-583e-9f67-fcbf7f74af46, 3:da2603d2-7929-5ce3-9217-cd86ad3f2955, 4:da91b8dd-87b7-56c9-b189-d662360d8d3d, 5:39306021-aad3-5ab4-b8ef-2089274e1c23, 6:bd25d6f5-da4c-58c1-8947-f810071a1b1b, 7:7b6df58f-aded-5fa8-986d-6c7e5508e301, 8:531c52e7-006a-57f4-97b8-e80f9b35e339, 9:23298043-752b-55c9-b05e-964933989819, 10:6426ad40-dfce-56a0-a538-b258af5ca11e
Failures: rerank_worsened_vs_dense

### VUE029 / dense_exact_offline

想让 watch 只往对象里检查两层，deep: 2 能直接用在 Vue 3.4 吗？数字形式的 deep 有版本要求吗？

Metrics: {"recall@1": 0.0, "hit_rate@1": 0.0, "recall@3": 0.5, "hit_rate@3": 1.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 0.5, "hit_rate@10": 1.0, "mrr@10": 0.5, "ndcg@10": 0.38685280723454163}
Evidence groups: {"evidence_group_coverage@1": 0.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 12.362700013909489, "dense_search": 0.3835999814327806, "cross_encoder_rerank": 0.0}
Top10: 1:90ec41b7-0670-58dd-a553-9f752e79a3f0, 2:e2800ff6-c50c-5f52-99b7-831b1347f720, 3:db2b988d-215d-57ec-bede-2f464494b832, 4:a69b781c-faf2-5e17-9bff-942dd6d58e1e, 5:1bbe5952-a953-5a71-8973-d627be6ae29d, 6:9b9c4f46-b134-59db-b70e-d22df5725d4a, 7:27fea3c0-b73a-5ed8-9c34-f9c6edd83405, 8:cb529efc-8e18-5ac6-bcc8-7ecae08520cd, 9:0cdb0dde-c1b3-5414-9864-a45588c5076a, 10:a61ced98-5f68-5f24-9fa9-0f0239cb5331
Failures: labeled_relevant_chunks_missing_at_10

### VUE029 / dense_rerank_offline

想让 watch 只往对象里检查两层，deep: 2 能直接用在 Vue 3.4 吗？数字形式的 deep 有版本要求吗？

Metrics: {"recall@1": 0.5, "hit_rate@1": 1.0, "recall@3": 0.5, "hit_rate@3": 1.0, "recall@5": 0.5, "hit_rate@5": 1.0, "recall@10": 0.5, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.6131471927654584}
Evidence groups: {"evidence_group_coverage@1": 1.0, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 12.362700013909489, "dense_search": 0.3835999814327806, "cross_encoder_rerank": 6325.586899998598}
Top10: 1:e2800ff6-c50c-5f52-99b7-831b1347f720, 2:27fea3c0-b73a-5ed8-9c34-f9c6edd83405, 3:90ec41b7-0670-58dd-a553-9f752e79a3f0, 4:f2dc5afd-1de3-5074-bac7-ba2e9febd667, 5:a69b781c-faf2-5e17-9bff-942dd6d58e1e, 6:9b9c4f46-b134-59db-b70e-d22df5725d4a, 7:0cdb0dde-c1b3-5414-9864-a45588c5076a, 8:db2b988d-215d-57ec-bede-2f464494b832, 9:21be7e89-4a62-56d5-99f4-0b1c65699a3c, 10:d91472a5-46be-5b6d-a55b-59468d69ba9b
Failures: labeled_relevant_chunks_missing_at_10

### VUE030 / dense_exact_offline

Vue 3.5 里我先 await 再调用 onWatcherCleanup 注册取消旧请求的回调，为什么不对？注册回调和真正取消请求是同一时刻吗？它和回调参数给的 onCleanup 限制一样吗？

Metrics: {"recall@1": 0.2, "hit_rate@1": 1.0, "recall@3": 0.6, "hit_rate@3": 1.0, "recall@5": 0.8, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.9818483242455303}
Evidence groups: {"evidence_group_coverage@1": 0.75, "evidence_group_coverage@3": 1.0, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 13.471300015226007, "dense_search": 0.44150001485832036, "cross_encoder_rerank": 0.0}
Top10: 1:5acc91a0-5fd7-5021-86c0-a9d2e4ee124e, 2:cb8f0eda-ad24-5450-936d-a2eef1905f3b, 3:93ee0ba2-4f0f-5338-b6c6-b02f9b42f907, 4:399b3a78-0f97-5021-ac15-5bb388f8260e, 5:fd72e98f-d467-5581-9e1b-8e9d70b55fed, 6:7bf3f492-a474-5abe-88ac-7194105f1099, 7:21609aa6-5817-5c26-ac68-59aca2eff30f, 8:e2800ff6-c50c-5f52-99b7-831b1347f720, 9:0cdb0dde-c1b3-5414-9864-a45588c5076a, 10:e788e5c1-ee63-5e5b-a656-42f846f3ed85
Failures: none

### VUE030 / dense_rerank_offline

Vue 3.5 里我先 await 再调用 onWatcherCleanup 注册取消旧请求的回调，为什么不对？注册回调和真正取消请求是同一时刻吗？它和回调参数给的 onCleanup 限制一样吗？

Metrics: {"recall@1": 0.2, "hit_rate@1": 1.0, "recall@3": 0.6, "hit_rate@3": 1.0, "recall@5": 0.8, "hit_rate@5": 1.0, "recall@10": 1.0, "hit_rate@10": 1.0, "mrr@10": 1.0, "ndcg@10": 0.9896062251871525}
Evidence groups: {"evidence_group_coverage@1": 0.5, "evidence_group_coverage@3": 0.75, "evidence_group_coverage@5": 1.0, "evidence_group_coverage@10": 1.0}
Stage ms: {"query_embedding": 13.471300015226007, "dense_search": 0.44150001485832036, "cross_encoder_rerank": 6190.357800020138}
Top10: 1:93ee0ba2-4f0f-5338-b6c6-b02f9b42f907, 2:5acc91a0-5fd7-5021-86c0-a9d2e4ee124e, 3:21609aa6-5817-5c26-ac68-59aca2eff30f, 4:cb8f0eda-ad24-5450-936d-a2eef1905f3b, 5:e2800ff6-c50c-5f52-99b7-831b1347f720, 6:399b3a78-0f97-5021-ac15-5bb388f8260e, 7:5d99a249-971f-57f8-a301-d07709e7901e, 8:6df6403f-8dea-58e9-bd6a-514c4cdf368e, 9:d91472a5-46be-5b6d-a55b-59468d69ba9b, 10:0cdb0dde-c1b3-5414-9864-a45588c5076a
Failures: none

