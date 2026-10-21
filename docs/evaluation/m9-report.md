# M9 人工数据评估报告

运行时间：2026-10-17T06:41:03.679155+00:00；模式：real；状态：complete。
数据集 SHA-256：`cfeb3c68b2803ff7f5c62fac819e7d8ae8e2f08609a110dffcc3e49f94602da2`。
源码指纹：`96f8a88f034615d46a0a9fbde6cc35b996ad7cf9a8105618c53323e20d38bd16`；HEAD：`b9afc490ece5a2fcdfe303e43961b41bc9401538`，包含未提交工作区。

范围：单次真实 CPU BGE / Reranker + DeepSeek；通过真实服务和 RLS 应用角色访问 PostgreSQL。不是 HTTP/SSE 延迟基准。
自动测试使用 Fake，不能与此处真实模型结果混算。没有额外 LLM judge。

## 规则代理结果

| 集合 | 样本数 | 规则任务通过率 | 错误 | 人工/模型辅助/未复核 |
| --- | ---: | ---: | --- | --- |
| dev/rag | 12 | 0.9167 | {} | 0/2/10 |
| dev/agent | 6 | 0.8333 | {} | 0/2/4 |
| holdout/rag | 12 | 1.0000 | {} | 0/4/8 |
| holdout/agent | 6 | 0.6667 | {'invalid_citation': 1} | 0/3/3 |

规则是词项/数值代理，不处理完整否定和语义，不能称为 Answer Correctness 或 Faithfulness。
R13 的冻结 facts 错写七天，实际人工资料为三十天：保留原规则失分，模型辅助复核独立说明；没有改参考答案或删除用例。

## 已复核指标（仅限相应复核子集）

| 集合/复核来源 | 正确性 | Faithfulness | 引用支持 | 任务完成 |
| --- | --- | --- | --- | --- |
| dev/rag/human | N/A (n=0) | N/A (n=0) | N/A (n=0) | N/A (n=0) |
| dev/rag/model_assisted | 1.0000 (n=2) | 1.0000 (n=2) | 1.0000 (n=2) | 1.0000 (n=2) |
| dev/agent/human | N/A (n=0) | N/A (n=0) | N/A (n=0) | N/A (n=0) |
| dev/agent/model_assisted | 0.5000 (n=2) | 1.0000 (n=1) | 1.0000 (n=1) | 0.5000 (n=2) |
| holdout/rag/human | N/A (n=0) | N/A (n=0) | N/A (n=0) | N/A (n=0) |
| holdout/rag/model_assisted | 1.0000 (n=4) | 1.0000 (n=4) | 1.0000 (n=4) | 1.0000 (n=4) |
| holdout/agent/human | N/A (n=0) | N/A (n=0) | N/A (n=0) | N/A (n=0) |
| holdout/agent/model_assisted | 0.3333 (n=3) | 1.0000 (n=1) | 1.0000 (n=1) | 0.3333 (n=3) |

复核子集不是随机样本，不外推总体。人工复核数量为零时不宣称“人工验收通过”；无事实拒答的 Faithfulness 为 N/A。

## 检索指标

| 集合 | 方法 | 有标注样本 | Recall@1 | Recall@5 | MRR@10 |
| --- | --- | ---: | ---: | ---: | ---: |
| dev | dense | 11 | 1.0000 | 1.0000 | 1.0000 |
| dev | sparse | 11 | 0.9091 | 0.9091 | 0.9091 |
| dev | rrf | 11 | 0.9091 | 1.0000 | 0.9545 |
| dev | rerank | 11 | 1.0000 | 1.0000 | 1.0000 |
| holdout | dense | 10 | 0.8500 | 1.0000 | 0.9500 |
| holdout | sparse | 10 | 0.9500 | 1.0000 | 1.0000 |
| holdout | rrf | 10 | 0.9500 | 1.0000 | 1.0000 |
| holdout | rerank | 10 | 0.9500 | 1.0000 | 1.0000 |

无答案/空KB不进入Recall/MRR分母。语料24条、候选30，召回易饱和；开发/保留问题共享同一小语料，保留集不是独立分布。

## 延迟与调用成本

| 模式 | n | median 秒 | max 秒 | LLM calls | prompt tokens | completion tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| rag | 24 | 1.094 | 1.547 | 23 | 7666 | 616 |
| agent | 12 | 1.702 | 3.469 | 21 | 15620 | 1764 |

冷加载及整个人工语料编码：35.468 秒。
逐题时间不含额外四路排名对比和冷加载；包含实际RAG/Agent服务调用。全部成本按provider usage报告，缺失必须标unknown，不估算费用。

## Agent 与拒答

工具选择符合任务约束：9/12。
参数通过Schema：12/12 次调用（没有提出调用的任务不进入参数分母）。
参数语义需逐条复核；Schema通过不能证明检索问题合适。A11/A12在此运行都使用不存在的文档ID，不能算真实跨租户评估；隔离由集成测试单独验证。
拒答规则仅检测否定词，可能将带限定条件的正常答案误判为拒答，真实表现见逐条记录与复核。

## 逐条结果

| ID | 集合 | 错误 | 规则任务通过 | 复核 |
| --- | --- | --- | --- | --- |
| R01 | dev | - | True | model_assisted |
| R02 | holdout | - | True | unreviewed |
| R03 | dev | - | True | unreviewed |
| R04 | holdout | - | True | model_assisted |
| R05 | dev | - | True | unreviewed |
| R06 | holdout | - | True | model_assisted |
| R07 | dev | - | True | unreviewed |
| R08 | holdout | - | True | unreviewed |
| R09 | dev | - | True | unreviewed |
| R10 | holdout | - | True | unreviewed |
| R11 | dev | - | True | unreviewed |
| R12 | holdout | - | True | unreviewed |
| R13 | dev | - | False | model_assisted |
| R14 | holdout | - | True | unreviewed |
| R15 | dev | - | True | unreviewed |
| R16 | holdout | - | True | unreviewed |
| R17 | dev | - | True | unreviewed |
| R18 | holdout | - | True | model_assisted |
| R19 | dev | - | True | unreviewed |
| R20 | holdout | - | True | unreviewed |
| R21 | dev | - | True | unreviewed |
| R22 | holdout | - | True | model_assisted |
| R23 | dev | - | True | unreviewed |
| R24 | holdout | - | True | unreviewed |
| A01 | dev | - | True | unreviewed |
| A02 | holdout | invalid_citation | False | model_assisted |
| A03 | dev | - | True | unreviewed |
| A04 | holdout | - | False | model_assisted |
| A05 | dev | - | False | model_assisted |
| A06 | holdout | - | True | unreviewed |
| A07 | dev | - | True | unreviewed |
| A08 | holdout | - | True | unreviewed |
| A09 | dev | - | True | model_assisted |
| A10 | holdout | - | True | model_assisted |
| A11 | dev | - | True | unreviewed |
| A12 | holdout | - | True | unreviewed |
