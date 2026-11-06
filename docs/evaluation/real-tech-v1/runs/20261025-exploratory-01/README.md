# real-tech-v1：第一轮探索性离线开发实验

**Exploratory / unverified。不是独立 Final，不是正式人工金标评测。**

使用现有 AI 辅助内容审核草案，不修改 human_reviewed、review_status 或相关标签。标签穷尽性未确认。
所有原始数据、candidates、review-proposal、content-review-draft、v2 历史产物及原有 metrics.py 均通过运行前后哈希核对。

## 文件

- [run.json](run.json)：58 条真实记录，逐题 Top10、Dense Top30、指标、事实组、阶段耗时和失败清单。
- [run.md](run.md)：完整逐题排名和指标、人类可读汇总。
- [verification.json](verification.json)：直接根据原始排名与冻结标签，以标准库独立复算指标、证据组覆盖率和管线 P95。

## 范围与固定参数

- 15 篇 Vue 3 官方中文 Markdown，215 个真实 Chunk，字符切分 1000/150。
- 29 条开发探索样本：24 条可回答、5 条无答案；排除 VUE026。
- 24 条可回答问题参与 Recall、Hit Rate、MRR、nDCG、Evidence Group Coverage 的宏平均。
- 5 条负样本单独计算空结果率。延迟统计包含全部 29 条问题。
- BGE-small-zh-v1.5，CPU、Embedding batch=32；Dense Top30。
- bge-reranker-base，CPU、batch=8、max_length=512；对相同 Dense Top30 重排，最终 Top10。
- 使用既有 BgeEmbedding、rerank、NumPy 精确余弦路径及 retrieval_metrics/aggregate；不使用 PostgreSQL 或 LLM。
- HF_HUB_OFFLINE=1、TRANSFORMERS_OFFLINE=1，从真实本地模型缓存读取，未使用模拟后端。
- 模型 revision、源码指纹、数据与标注哈希、硬件线程设置见 run.json。
- 单次顺序实验，无参数搜索，无重复运行选优。

## 可回答问题结果（n=24）

| 策略 | Recall@1 | Recall@3 | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | EGC@10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Dense | 0.114286 | 0.282044 | 0.430655 | 0.619544 | 0.546875 | 0.478561 | 0.833333 |
| Dense + Rerank | 0.206944 | 0.519841 | 0.642460 | 0.754663 | 0.750000 | 0.658565 | 0.902778 |

| 策略 | EGC@1 | EGC@3 | EGC@5 | EGC@10 |
| --- | ---: | ---: | ---: | ---: |
| Dense | 0.315972 | 0.506944 | 0.673611 | 0.833333 |
| Dense + Rerank | 0.409722 | 0.774306 | 0.861111 | 0.902778 |

EGC@K = 前 K 个结果覆盖的必要事实组数 / 必要事实组总数；组内任一直接支持 Chunk 命中即覆盖，一个 Chunk 可覆盖多组。总体对可回答问题宏平均。
Recall 仍以全部已标注相关 Chunk 为分母，未替换原公式。替代证据较多时，Recall 低于 EGC 是两者统计对象不同，不是公式冲突。

## 无答案结果（每策略 n=5）

两种策略空结果率均为 0/5 = 0。VUE021～VUE025 均返回结果。
当前实验没有引入分数阈值或拒检规则；该结果不是 LLM 最终拒答正确率。

## CPU 延迟（毫秒，n=29）

| 阶段 | P50 | P95 |
| --- | ---: | ---: |
| Query Embedding（两策略共享） | 10.528 | 13.216 |
| Dense 过滤、距离计算与排序（共享） | 0.500 | 0.648 |
| Cross-Encoder 重排 | 6339.126 | 6609.657 |
| Dense 管线总计 | 11.085 | 13.684 |
| Dense + Rerank 管线总计 | 6352.024 | 6622.647 |

总耗时按每题实际阶段相加后计算分位数，不能将各阶段的 P95 直接相加。
模型冷加载、整批语料编码与预热约 10.418 秒，单独记录，不计入逐题时间。
不包含数据库、HTTP、鉴权、LLM、SSE，也不包括结果文件写入；不能称为生产请求延迟。
执行环境：12 个逻辑 CPU，PyTorch CPU 后端，torch_threads=6；完整环境见原始记录。

## 失败案例

以下类别可能重叠，“未召回相关 Chunk”表示没有找齐全部候选正标签，不必然等于无法回答。

| 类别 | Dense | Dense + Rerank |
| --- | ---: | ---: |
| Top10 未找齐全部相关 Chunk | 17 | 11 |
| Top10 存在未覆盖必要事实组 | 5 | 3 |
| 负样本仍返回结果 | 5 | 5 |
| 重排后至少一个对照指标恶化 | 不适用 | 4 |

未覆盖组：

- Dense：VUE002（G1、G2）、VUE011（G1、G2）、VUE014（G2、G3）、VUE020（G3）、VUE027（G1、G2）。
- Dense + Rerank：VUE011（G1、G2）、VUE020（G3）、VUE027（G1、G2）。

重排恶化：

- VUE012：MRR@10、nDCG@10 下降。
- VUE015：Recall@10、MRR@10、nDCG@10 下降。
- VUE018：nDCG@10 下降。
- VUE028：MRR@10、nDCG@10 下降。

完整缺失 Chunk ID、Top10 排名、分组缺失和逐题耗时见 run.json 的 records / failure_cases。
本轮仅报告现象，没有根据这些开发结果修改题目、标签、模型或检索参数。

## 运行方式

在仓库根目录执行；下一次必须使用新的输出目录，入口拒绝覆盖已有探索性结果。

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
.\.venv\Scripts\python.exe -B -m scripts.evaluation.experiment --root tests/fixtures/evaluation/real-tech-v1 --output docs/evaluation/real-tech-v1/runs/20261025-exploratory-01/run.json --mode offline --split dev --dataset-kind real-tech-exploratory --allow-unverified-exploratory
```

轻量校验：新增适配与事实组计算单元测试 2 项通过；58 条真实记录的逐题及汇总指标独立复算一致。
