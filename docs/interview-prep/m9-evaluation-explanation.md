# M9：面试讲解材料

## 30秒项目说明

我在个人多租户RAG/Agent项目中加入了精简评估与本地可观测性：冻结24个RAG问题和12个Agent任务，用真实PostgreSQL、BGE和DeepSeek记录检索、工具行为、答案与实际模型证据；自动测试使用Fake，不依赖外部模型。评估区分规则代理、模型辅助复核、人工标注和未复核，Trace默认不记录正文或凭证。项目部分实现使用Codex辅助，个人能解释的设计与排错范围应如实说明。

## 1. 首先修复了什么

此前116 passed、150 errors不是150个业务断言分别失败，而是共同的数据库fixture失败。
完整traceback指向角色初始化；现有安全初始化脚本返回ConnectionRefusedError；Docker引擎未启动。Docker Desktop随后又因sailor-ingest.sock访问错误崩溃。
用户恢复Docker后，PostgreSQL healthy，角色初始化、迁移、RLS测试正常，266项基线在77.45秒内通过。没有跳过集成测试或关闭RLS。
M9新增27项测试后，最终全量为293 passed（73.70秒）；pip check、alembic check、git diff --check通过。原Git暂存补丁与历史迁移哈希保持一致，没有自动提交。

## 2. 指标怎么解释

| 指标 | 分母/含义 | 常见误区 |
| --- | --- | --- |
| Recall@K | topK命中的相关Chunk数 / 标注相关Chunk总数 | 无答案不记为0；多个相关Chunk时Recall@1不一定能到1 |
| MRR@K | 首个相关结果倒数排名，跨题平均 | 不是所有相关结果的平均排名 |
| 规则正确性代理 | 参考事实别名/数字命中，按题统计 | 不理解否定，不能当语义正确率 |
| Answer Correctness | 对问题是否完整且无矛盾：0/0.5/1，由独立复核标注 | 正确答案不一定有实际Context支持 |
| Faithfulness | 已标注事实中被本次实际证据支持的比例，按样本再平均 | 无事实拒答为N/A；不使用模型没见过的原文 |
| 引用支持 | 标注的引用关联事实中，实际证据支持的比例 | `[S1]`存在不等于内容支持 |
| 工具选择 | 提出调用集合满足任务允许/必需工具约束 | 不强制唯一调用顺序 |
| 参数有效性 | Schema合法调用 / 实际提出调用 | 没调用工具不进入分母，不能借此获得任务满分 |
| 任务完成 | 工具行为、答案、证据和错误状态综合判断 | Graph completed不代表问题解决 |

支持复核导入，但校验器只能验证引用的quote确实出现在模型可见证据、record hash一致，不能自动证明语义蕴含或标注完整性。人工/模型辅助结果分栏，不合并伪装。

## 3. 本次真实结果

- 冻结版本：m9-artificial-v1；24条人工资料；RAG开发/保留各12题，Agent各6题。
- RAG规则任务通过23/24，开发集11/12、保留集12/12。唯一失分R13来自规则标注错误（三十天误写七天），保留原始失分。
- Agent规则任务通过9/12，开发5/6、保留4/6；错误包括一次invalid_citation和两次未检索导致任务未完成。
- Agent工具选择符合9/12；实际12次工具调用参数Schema均合法。不能说Agent参数/任务“100%可靠”。
- 检索保留集Dense Recall@1=0.85、MRR@10=0.95；Hybrid+Rerank为0.95、1.0；两者Recall@5均1.0。R22需要两个相关Chunk，top1最多覆盖一半。
- 11条由Codex进行的模型辅助复核、0条人工复核、25条未复核。8条有事实的复核样本均支持，但样本经过选择，不作为总体Faithfulness。
- 没有调用额外judge模型；无需多模型评审平台。真实生成使用DeepSeek，模型辅助复核来自本次开发审阅，明确区分来源。

这是一份用于诊断的小数据集，不是生产benchmark。开发和保留问题共享语料，且不少内容来自既有M7样本；保留仅表示此次实现未用其调整Prompt，不代表完全未见过的独立分布。

## 4. 成本与性能

实际44次DeepSeek调用均收到usage：输入23,286、输出2,380、总计25,666 Token。没有当前账单单价依据，不给人民币费用估算。RAG23次调用，空KB不调用；Agent21次。
冷加载及语料embedding35.468秒。RAG服务median1.094秒/max1.547秒；Agent median1.702秒/max3.469秒。额外四路检索对比耗时不包含在服务延迟中；测试未经过HTTP，不声称SSE首字延迟或p95吞吐。

本地Trace记录阶段、耗时、候选数量、调用与Token；流式usage的最终空choices chunk单独解析，不能误当无效回答。缺失usage标记不完整，不把未知消耗当0；汇总数字只是已知部分。

## 5. 典型失败怎么讲

1. **检索层**：E1001的Dense第一名错误，FTS修正；远程办公问题的RRF反而降序，Rerank恢复。不是每层都提高质量。
2. **Agent层**：有知识却未调用工具，服务端安全拒答，任务失败；引用防护拒绝结果可以是安全成功、产品失败。
3. **评估层**：R13参考规则错误，不能把模型正确回答判成真实质量问题；保持冻结版本，写erratum而非悄悄改分。
4. **成本层**：简单问题也会多次检索，Agent增加Token和延迟，不必替代稳定普通RAG路径。
5. **数据范围**：A12实际用了不存在ID，不能声称测试了真实跨租户任务；RLS隔离仍由真实数据库集成测试保证。

预算/超时属于可注入程序用例，真实本次没有发生，不捏造真实失败。

## 6. 设计取舍与安全

- 不搭建监控服务，不引入业务表；本地JSONL轮转文件，128个span上限；默认关闭，丢失Trace不能改变业务成功/失败。
- 不捕获函数参数/返回值；不落用户正文、JWT、密码、工具参数或异常原文。安全Trace与人工评估记录是不同产物。
- ContextVar隔离并发；子span关联父span。模型推理和日志落地不新增数据库事务，M6 RLS继续有效。
- LangSmith仅提供显式离线白名单导出，默认只打印安全预览；未配置凭证、未进行真实上传。本版没有“已上线LangSmith监控”成果。
- 不改原HTTP/SSE协议。SSE仍然是过程实时、答案校验后分片，不是逐Token答案；没有思维链输出。

## 7. 如何复现

```powershell
# 真实数据库与全部离线自动测试（不要与真实评估并行）
docker compose up -d --wait
.venv\Scripts\python.exe -m pytest -o addopts=

# 真实人工评估：独立测试库，真实本地模型与DeepSeek，有网络及Token成本
.venv\Scripts\python.exe -m scripts.evaluate_m9 --real

# 离线评分与报告，不访问网络、数据库或模型
.venv\Scripts\python.exe -m scripts.evaluate_m9 --score docs/evaluation/m9-run.json --reviews docs/evaluation/m9-reviews.json
.venv\Scripts\python.exe -m scripts.evaluation.report docs/evaluation/m9-run.json --reviews docs/evaluation/m9-reviews.json --output docs/evaluation/m9-report.md

# 仅预览安全导出，不上传
.venv\Scripts\python.exe -m scripts.export_m9_langsmith docs/evaluation/m9-run.json
```

真实评估每次写入独立`.data/evaluations/m9-...`目录，不覆盖旧报告；临时租户用运行角色查询、维护角色创建/清理，仅删除自己创建的数据。数据集SHA按LF文本规范化，Windows换行不造成假漂移。

新增human复核时填写真实reviewer，引用原始record hash，列出答案中的全部事实及实际证据quote。不要把本次model_assisted改名为human。

## 8. 下一步改进方向（本版未实施）

完成剩余人工复核、独立标注一致性检查；以新版本修正R13和A12数据缺陷；扩充独立真实分布的脱敏样本；记录未通过引用验证的人工评估候选回答以更精确诊断；比较强制检索策略与当前工具自由选择的成本和成功率。只有评估支持才修改Prompt/检索流程。
未做在线监控告警、多模型judge、额外Agent功能或M10前端。
