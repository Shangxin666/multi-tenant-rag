# real-tech-v1：Vue 3 官方中文文档候选评测集

## 状态与范围

本目录是第一阶段真实语料与候选问题准备产物，不是已审核的最终评测集。
15 份原始 Markdown 来自同一个固定 Commit 的官方中文仓库，保留全部标题、章节、代码示例、版本提示及原始路径。
没有下载图片、运行文档中的脚本、生成 Embedding、调用 Reranker、访问 PostgreSQL 或执行 Agent。
30 条候选问题均由 AI 辅助拟定，`human_reviewed=false`、`review_status=unverified`、`eligible_for_trusted_evaluation=false`。
结构校验成功不代表答案、相关性、证据完整性或负样本真实性已获人工认可。

## 来源与许可

- 来源：https://github.com/vuejs-translations/docs-zh-cn
- 固定 Commit：`418f5ae6e15c7a90beae017e44d58dac3d93ad95`
- Commit 通过只读 `git ls-remote ... refs/heads/main` 获取；不是 Vue 产品版本标签。
- 原始 Markdown 按固定 Commit 下载，字节未修改；URL、SHA256、下载时间见 `upstream.json` 与 `sources.json`。
- 版权：Copyright (c) 2019-present, Yuxi (Evan) You and Vue documentation contributors。
- **两处许可声明不一致：该固定 Commit 的中文 README.md 第 51 行声明 CC BY-NC-SA 4.0，根目录 LICENSE 对非图片内容声明 CC BY 4.0。两份原文均保存，不选择较宽松声明来忽略中文译文条件。**
- 本中文语料及包含原文的派生数据按 README 的 **CC BY-NC-SA 4.0** 条件处理：署名、非商业性使用、标明修改；如分发改编数据，遵守相同方式共享要求。该处理策略不裁定上游两处声明的优先级，也不表示取得商业使用授权。
- 保留完整许可 `licenses/upstream-LICENSE.txt` 与仓库说明 `licenses/upstream-README.md`，并为每份文档与证据提供固定来源链接。
- 文档、引文与切分内容保留上游版权及中文译者归属；派生物的变动为解析、切分、位置标注和候选问答编写，不暗示上游认可本评测。详见 `licenses/NOTICE.md`。
- 图片有独立版权条件，未收集图片文件；Markdown 中原有图片链接仍保留，但不作为评测证据。
- 未来更换 Commit 或来源时必须重新核对许可，不将本次的资料使用条件外推到其他快照。

## 真实解析和切分

直接调用当前项目的 `parse_document(path, 'markdown', 200, 2_000_000)` 与
`split_sections(sections, 1000, 150, 5000)`，不另写切分器、不人为重复语料。
Markdown 解析器目前保留原始标记，包括 Vue 文档的 HTML 容器、选项式/组合式双示例、外链及代码围栏；未运行 VitePress 渲染或补入外链内容。
证据与 Chunk 的字符位置以解析输出为准，采用 Unicode 字符、LF 换行及左闭右开范围；源文件行号从 1 开始。
标题路径与章节锚点由评测侧扫描源 Markdown 补充，不修改生产解析器或切分器。
Chunk 可能跨章节，也可能截断代码围栏，这是当前生产切分行为，不能宣称结构感知切分。

## 文件导航

- `statistics.json`：逐文档 Chunk 数、单个知识库候选总数和题目分类。
- `REVIEW.md`：30 条候选题的答案、评价点、原文、章节和 Chunk ID，供人工逐条审核。
- `candidate_specs.json`：问题起草稿、原始证据行区间；可审计生成依据。
- `annotations/candidates.jsonl`：候选问题，包含审核状态、证据位置、证据组和相关 Chunk ID。
- `dataset.json`：文档、Chunk、候选问题的统一快照；不兼容当前 synthetic 专用验证器，不能直接送入现有可信实验。
- `parsed.jsonl` / `chunks.jsonl`：真实解析、切分结果与位置映射。
- `sources.json` / `upstream.json`：来源、Commit、许可、URL、文件哈希。
- `manifest.json` / `dataset.sha256`：本地文件、解析代码、依赖和历史 v2 文件的哈希。
- `validation.json`：仅结构性验证结果。
- `fetch_sources.py`：固定 Commit 的选择性下载脚本，拒绝覆盖已有快照。
- `prepare.py`：准备和轻量验证入口；不会导入 Embedding 或 Reranker。

## 证据与计分约束

先根据原文段落和章节起草证据，再映射到该文档内所有包含该段原文的真实 Chunk。
这是机械映射，不是精确包含即代表语义相关的最终标注方法。
`relevant_chunk_ids` 是待审候选集合，`relevance_complete=false`；其它章节和文档中可能存在可替代证据，必须人工排查。
`evidence_groups` 表达初步必要事实与替代证据，仍待人工重组；`distractor_evidence` 尚未标注，不代表不存在干扰。
负样本没有支持证据，故 `source_document_ids/evidence/relevant_chunk_ids` 为空；另记完整审核语料范围、搜索词和字面命中。
检索词无命中不证明不存在语义答案，负样本也全部待审。
版本边界仅依据这份 Vue 3 快照中的 3.4/3.5 说明，不混入 Vue 2 文档，也不是历史运行时兼容性测试。

## 知识库与划分

所有 30 条候选问题使用同一个评测租户和知识库，候选范围是全部 15 篇文档的全部真实 Chunk。
没有按题目挑选小语料，没有复制文档到多个知识库凑数。
当前 `split=unassigned`，尚无 Dev/Final；必须先审核问题、文档家族和跨文档证据依赖，再冻结划分。
原有 `tests/fixtures/evaluation/v2` 和 `docs/evaluation/v2` 的历史文件哈希在 manifest 中保存并校验。

## 本地复核

在仓库根目录执行（不下载、不运行模型、不访问数据库）：

```powershell
.\.venv\Scripts\python.exe -B tests/fixtures/evaluation/real-tech-v1/prepare.py validate
```

该命令重新解析切分并核对内容、来源哈希、证据位置、知识库范围及 v2 历史文件哈希，写入本目录的结构校验结果。
`build` 与下载脚本默认拒绝覆盖已有快照；审核后的变更应形成明确的新版本及新的 manifest，不覆盖冻结实验数据。
