"""Rebuild a human-readable report from immutable run records and optional reviews."""
import argparse
import json
from pathlib import Path
import statistics
from scripts.evaluation.scoring import summarize


def render(run: dict, reviews: dict) -> str:
    rows=run['records']
    lines=['# M9 人工数据评估报告','',f"运行时间：{run['started_at']}；模式：{run['mode']}；状态：{run['status']}。",
        f"数据集 SHA-256：`{run['dataset_hash']}`。",f"源码指纹：`{run['source_hash']}`；HEAD：`{run['code_head']}`，包含未提交工作区。",
        '', '范围：单次真实 CPU BGE / Reranker + DeepSeek；通过真实服务和 RLS 应用角色访问 PostgreSQL。不是 HTTP/SSE 延迟基准。',
        '自动测试使用 Fake，不能与此处真实模型结果混算。没有额外 LLM judge。',
        '', '## 规则代理结果', '', '| 集合 | 样本数 | 规则任务通过率 | 错误 | 人工/模型辅助/未复核 |', '| --- | ---: | ---: | --- | --- |']
    groups=summarize(rows,reviews)
    for name,g in groups.items():
        lines.append(f"| {name} | {g['n']} | {g['rule_task_pass_rate']:.4f} | {g['errors']} | {g['human_reviewed']}/{g['model_assisted_reviewed']}/{g['unreviewed']} |")
    lines+=['','规则是词项/数值代理，不处理完整否定和语义，不能称为 Answer Correctness 或 Faithfulness。',
        'R13 的冻结 facts 错写七天，实际人工资料为三十天：保留原规则失分，模型辅助复核独立说明；没有改参考答案或删除用例。',
        '', '## 已复核指标（仅限相应复核子集）','', '| 集合/复核来源 | 正确性 | Faithfulness | 引用支持 | 任务完成 |','| --- | --- | --- | --- | --- |']
    for name,g in groups.items():
        for reviewer in ('human','model_assisted'):
            cells=[]
            for metric in ('answer_correctness','faithfulness','citation_support','task_completed'):
                value=g[f'{reviewer}/{metric}']
                cells.append(f"{value['mean']:.4f} (n={value['n']})" if value['n'] else 'N/A (n=0)')
            lines.append('| '+name+'/'+reviewer+' | '+' | '.join(cells)+' |')
    lines+=['','复核子集不是随机样本，不外推总体。人工复核数量为零时不宣称“人工验收通过”；无事实拒答的 Faithfulness 为 N/A。',
        '', '## 检索指标','', '| 集合 | 方法 | 有标注样本 | Recall@1 | Recall@5 | MRR@10 |','| --- | --- | ---: | ---: | ---: | ---: |']
    for split in ('dev','holdout'):
        for method in ('dense','sparse','rrf','rerank'):
            selected=[r['retrieval'][method] for r in rows if r['split']==split and method in r['retrieval'] and r['retrieval'][method]['1']['recall'] is not None]
            if selected:
                vals=[statistics.mean(r[str(k)][metric] for r in selected) for k,metric in ((1,'recall'),(5,'recall'),(10,'mrr'))]
                lines.append(f"| {split} | {method} | {len(selected)} | "+' | '.join(f'{v:.4f}' for v in vals)+' |')
    lines+=['','无答案/空KB不进入Recall/MRR分母。语料24条、候选30，召回易饱和；开发/保留问题共享同一小语料，保留集不是独立分布。',
        '', '## 延迟与调用成本','', '| 模式 | n | median 秒 | max 秒 | LLM calls | prompt tokens | completion tokens |', '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for mode in ('rag','agent'):
        selected=[r for r in rows if r['mode']==mode]
        costs={k:sum(r['trace']['usage'][k] for r in selected) for k in ('calls','reported_calls','prompt_tokens','completion_tokens')}
        if selected:
            lines.append(f"| {mode} | {len(selected)} | {statistics.median(r['seconds'] for r in selected):.3f} | {max(r['seconds'] for r in selected):.3f} | {costs['calls']} | {costs['prompt_tokens']} | {costs['completion_tokens']} |")
    lines+=[f"\n冷加载及整个人工语料编码：{run.get('cold_load_and_corpus_embedding_seconds',0):.3f} 秒。",
        '逐题时间不含额外四路排名对比和冷加载；包含实际RAG/Agent服务调用。全部成本按provider usage报告，缺失必须标unknown，不估算费用。',
        '', '## Agent 与拒答', '']
    agent=[r for r in rows if r['mode']=='agent']
    calls=[c for r in agent for c in r['calls']]
    lines += [f"工具选择符合任务约束：{sum(r['rules']['tool_selection_pass'] for r in agent)}/{len(agent)}。",
              f"参数通过Schema：{sum(c['valid'] for c in calls)}/{len(calls)} 次调用（没有提出调用的任务不进入参数分母）。",
              '参数语义需逐条复核；Schema通过不能证明检索问题合适。A11/A12在此运行都使用不存在的文档ID，不能算真实跨租户评估；隔离由集成测试单独验证。',
              '拒答规则仅检测否定词，可能将带限定条件的正常答案误判为拒答，真实表现见逐条记录与复核。',
              '', '## 逐条结果', '', '| ID | 集合 | 错误 | 规则任务通过 | 复核 |', '| --- | --- | --- | --- | --- |']
    for r in rows:
        lines.append(f"| {r['case_id']} | {r['split']} | {r['error'] or '-'} | {r['rules']['task_rule_pass']} | {reviews.get(r['case_id'],{}).get('reviewer_type','unreviewed')} |")
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('--reviews',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    output=render(json.loads(args.run.read_text(encoding='utf-8')),json.loads(args.reviews.read_text(encoding='utf-8')) if args.reviews else {})
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(output,encoding='utf-8')
