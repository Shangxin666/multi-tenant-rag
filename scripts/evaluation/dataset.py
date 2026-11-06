"""Deterministic synthetic business corpus using the production parser/splitter.

Generation and validation never use retrieval rankings or question text to label.
"""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import random
from uuid import UUID, uuid5

from app.modules.documents.ingestion.parsers import parse_document
from app.modules.documents.ingestion.chunking import split_sections

ROOT = Path(__file__).resolve().parents[2]
DEFAULT = ROOT / 'tests/fixtures/evaluation/v2'
NS = UUID('d37183ea-ad17-48d1-a351-44133e4b9101')
SIZE, OVERLAP = 1000, 150


def stable(value):
    return str(uuid5(NS, value))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


TOPICS = [
    ('人事', '带薪年假额度', '天', '申请提前量', '工作日', '直属经理', '考勤记录'),
    ('财务', '差旅住宿限额', '元', '报销截止时限', '天', '财务主管', '电子发票'),
    ('设备', '额定输入电压', '伏', '检修周期', '天', '设备工程师', '绝缘测试记录'),
    ('平台', 'API每分钟限额', '次', '令牌有效期', '小时', '平台管理员', '调用审计记录'),
    ('数据', '备份保留期限', '天', '恢复演练周期', '天', '数据库管理员', '校验摘要'),
    ('支持', '服务响应时限', '分钟', '升级等待时限', '分钟', '值班主管', '工单编号'),
]


def generate(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    (root / 'corpus').mkdir(exist_ok=True)
    docs, chunks, facts, entities = [], [], {}, []
    for i in range(60):
        topic, field, unit, field2, unit2, owner, attachment = TOPICS[i % 6]
        entity = f'{topic}-方案-{i:03d}'
        split = 'dev' if i < 40 else 'final'
        tenant = stable(f'tenant:{i % 2}')
        kb = stable(f'kb:{tenant}:{split}')
        entities.append(dict(entity=entity, tenant_id=tenant, knowledge_base_id=kb, split=split))
        value, value2 = 12 + i * 3, 3 + i * 2
        clauses = [f'{entity}的{field}为{value}{unit}。',
                   f'{entity}的{field2}为{value2}{unit2}。',
                   f'{entity}由{owner}审批，必须提交{attachment}。']
        facts[entity] = clauses
        for kind in range(3):
            # Distinct effective policy, procedure and exception records, not text replication.
            paragraphs = [f'synthetic 模拟业务资料；{entity}；主题：{topic}；文档类型：{kind}。']
            if kind == 0:
                paragraphs += [clauses[0], f'{entity}仅适用于已签署该方案的正式业务单元；相邻编号方案具有独立合同，不能套用其额度。结算按生效月份核对，不追溯变更已经关闭的账期。',
                               f'{entity}的变更流程要求责任人发起版本申请，审核者对适用对象、计算口径与生效日期逐项签字。若申请缺少适用范围，审批退回补充，原版本继续有效。']
            elif kind == 1:
                paragraphs += [clauses[1], clauses[2], f'{entity}执行前由经办人检查凭证编号和申请人身份；执行后将结果写入业务台账。凭证不完整时先暂停处理，由原申请人补齐材料，不以口头说明替代。']
            else:
                paragraphs += [f'{entity}的临时试点额度为{value+9}{unit}，此数值仅用于沙箱演练，不能用于正式方案的{field}。',
                               f'{entity}的紧急流程由两位授权值班人共同复核。临时处理结束后两个工作日内补交审批说明，记录触发原因、影响范围和恢复时间。']
            # Independent operational knowledge creates meaningful long documents.
            processes = [
                ('版本归档', f'{entity}的历史版本保存于只读归档区，归档索引包含生效月份、审批单号和经办部门。撤销方案需注明替代版本，历史审批记录仍可审计。查询历史数据必须选择对应月份，不使用最新版本覆盖原记录。'),
                ('争议复核', f'{entity}发生争议时由业务责任部门登记异议，复核人比对原始凭证与审批快照。复核期间仅冻结争议部分，其他已核实项目正常处理。复核结论应说明采用的版本和证据，并通知原申请人确认。'),
                ('异常监控', f'{entity}出现重复申请时使用业务流水号合并核对，保留首次提交时间。监控只提示异常，不自动扩大授权范围。人工确认误报后记录原因；确认违规后提交审计流程，不直接删除历史证据。'),
                ('职责交接', f'{entity}责任人离岗前移交待办清单、审批权限及未解决风险。接任人核对清单后签收，系统管理员随后回收旧权限。交接期间所有操作继续使用个人账号，禁止共享账号处理审批。'),
                ('恢复验收', f'{entity}在流程中断后按台账重新核对最后成功步骤。恢复操作需要先确认没有重复执行，再完成剩余任务。验收人检查凭证、权限和结果一致性，形成可追溯记录后关闭事件。'),
                ('权限申请', f'{entity}的新经办人须通过实名申请取得最小必要权限，审批人与经办人不能是同一人。权限有效期跟随岗位任职期限，临时授权到期自动失效。审计人员仅有只读访问权，不能修改审批结论或替换凭证。'),
                ('数据更正', f'{entity}已结案记录发现录入错误时，提交更正单并关联原流水号。更正只追加新版本，不覆盖原始材料。主管确认更正原因后发布修订台账，原审批人收到通知，对金额或额度变化重新确认。'),
                ('服务降级', f'{entity}依赖系统不可用时启用离线登记模板，登记时间、操作人及原始请求摘要。恢复后按提交时间顺序补录，逐条核验幂等键防止重复。离线流程继续遵守原有额度和审批权限，不能作为绕过限制的理由。'),
                ('保密分级', f'{entity}的业务资料按内部资料管理，对外提供前移除个人身份与授权信息。供应商只能取得与履约相关的摘要，不能访问其他方案。导出操作留下审计日志，资料接收方需要说明使用目的与保管责任。'),
                ('季度检查', f'{entity}每季度抽查已关闭事项，检查凭证完整性、审批时点和结果一致性。抽样发现系统性缺陷时扩展检查范围，由流程负责人制定整改计划。整改结束后独立复核，未通过复核的事项继续保持开放状态。'),
            ]
            for j, (title, body) in enumerate(processes):
                # Vary document length and section placement without padding repeated text.
                if j < 8 + (i + kind) % 3:
                    paragraphs += [f'第{j+2}节 {title}', body]
            is_html = (i + kind) % 3 == 0
            filename = f'corpus/{i:03d}-{kind}.' + ('html' if is_html else 'md')
            content = '<html><head><title>synthetic</title></head><body>' + ''.join(f'<p>{html.escape(p)}</p>' for p in paragraphs) + '</body></html>' if is_html else '\n\n'.join(paragraphs)
            path = root / filename
            path.write_bytes(content.encode('utf-8'))
            did = stable(f'doc:{tenant}:{entity}:{kind}')
            doc = dict(id=did, tenant_id=tenant, knowledge_base_id=kb, entity=entity, split=split,
                       path=filename, source_type='html' if is_html else 'markdown', synthetic=True, sha256=sha(path.read_bytes()))
            docs.append(doc)
            for draft in split_sections(parse_document(path, doc['source_type'], 200, 2_000_000), SIZE, OVERLAP, 5000):
                chunks.append(dict(id=stable(f'chunk:{did}:{SIZE}:{OVERLAP}:{draft.chunk_index}:{sha(draft.content.encode())}'),
                                   document_id=did, tenant_id=tenant, knowledge_base_id=kb,
                                   chunk_index=draft.chunk_index, content=draft.content, metadata=draft.metadata))
    categories = ['exact'] * 30 + ['paraphrase'] * 24 + ['multi_evidence'] * 24 + ['distractor'] * 18 + ['unanswerable'] * 12 + ['boundary'] * 12
    random.Random(20261024).shuffle(categories)
    cases = []
    for n, category in enumerate(categories):
        e = entities[n % 60]
        entity = e['entity']
        topic, field, unit, field2, unit2, owner, attachment = TOPICS[n % 60 % 6]
        selected = facts[entity][:1]
        question = f'{entity}的{field}是多少？'
        if category == 'paraphrase':
            question = f'我们执行{entity}，想确认正式规定里{field}的具体数值。'
        elif category == 'multi_evidence':
            selected = facts[entity][:]
            question = f'请整合{entity}的正式{field}、{field2}及审批人与所需材料。'
        elif category == 'distractor':
            question = f'{entity}正式方案的{field}是多少？请区分试点沙箱额度和相邻编号。'
        elif category == 'unanswerable':
            question = f'{entity}负责的火星基地氧气储备是多少？'
            selected = []
        if n >= 60:
            question = {
                'exact': f'{entity}适用的{field}按什么数值执行？',
                'paraphrase': f'关于{entity}，请说明当前有效{field}标准。',
                'multi_evidence': f'办理{entity}时，{field}和{field2}分别是多少，需要谁审批和哪些凭证？',
                'distractor': f'不要把试点当作正式要求：{entity}实际生效的{field}规定是什么？',
                'unanswerable': f'想了解{entity}对应火星基地的氧气存量，资料里有多少？',
                'boundary': f'{entity}适用的{field}按什么数值执行？',
            }[category]
        scope = {k: e[k] for k in ('tenant_id', 'knowledge_base_id', 'split')}
        forbidden = []
        if category == 'boundary':
            forbidden = [d['id'] for d in docs if d['entity'] == entity]
            if n % 2:
                scope['tenant_id'] = stable(f'tenant:{1 - n % 60 % 2}')
                scope['knowledge_base_id'] = stable(f"kb:{scope['tenant_id']}:{e['split']}")
            else:
                scope['knowledge_base_id'] = stable(f"kb:{e['tenant_id']}:{'final' if e['split']=='dev' else 'dev'}")
            selected = []
        evidence = [dict(chunk_id=c['id'], document_id=c['document_id'], quote=quote) for quote in selected for c in chunks if c['tenant_id']==e['tenant_id'] and c['knowledge_base_id']==e['knowledge_base_id'] and quote in c['content']]
        cases.append(dict(id=f'Q{n+1:03d}', question=question, expected_answer=''.join(selected) if selected else '授权知识库中没有该问题的证据。',
                          relevant_document_ids=sorted({v['document_id'] for v in evidence}), relevant_chunk_ids=sorted({v['chunk_id'] for v in evidence}),
                          **scope, entity=entity, category=category, difficulty='hard' if category in ('multi_evidence','distractor','boundary') else 'medium',
                          answerable=bool(selected), evidence=evidence, forbidden_document_ids=forbidden,
                          annotation={'method':'synthetic structured fact + exhaustive exact evidence containment', 'human_reviewed':False,
                                      'required_quotes':selected, 'negative_reason': 'out_of_scope' if category=='boundary' else 'closed_world_missing_fact' if not selected else None}))
    data = dict(version='synthetic-business-v2.0', chunk_size=SIZE, chunk_overlap=OVERLAP,
                split_policy='entity-disjoint; dev entities 000-039, final 040-059; separate knowledge bases',
                documents=docs, chunks=chunks, cases=cases)
    write_json(root / 'dataset.json', data)
    (root / 'dataset.sha256').write_text(sha((root / 'dataset.json').read_bytes())+'\n', encoding='ascii')
    return validate(root)


def load(root=DEFAULT):
    raw = (root / 'dataset.json').read_bytes()
    if sha(raw) != (root / 'dataset.sha256').read_text().strip():
        raise ValueError('Dataset hash mismatch; do not edit frozen labels')
    return json.loads(raw)


def validate(root=DEFAULT):
    data = load(root)
    docs = {d['id']: d for d in data['documents']}
    chunks = {c['id']: c for c in data['chunks']}
    if len(docs)!=len(data['documents']) or len(chunks)!=len(data['chunks']):
        raise ValueError('Duplicate corpus IDs')
    rebuilt = []
    for d in docs.values():
        path = root / d['path']
        if not d['synthetic'] or sha(path.read_bytes())!=d['sha256']:
            raise ValueError('Source hash/synthetic mismatch')
        drafts = split_sections(parse_document(path,d['source_type'],200,2_000_000),data['chunk_size'],data['chunk_overlap'],5000)
        for draft in drafts:
            cid = stable(f"chunk:{d['id']}:{data['chunk_size']}:{data['chunk_overlap']}:{draft.chunk_index}:{sha(draft.content.encode())}")
            c = chunks.get(cid)
            if c is None or c['content']!=draft.content or c['document_id']!=d['id'] or c['tenant_id']!=d['tenant_id'] or c['knowledge_base_id']!=d['knowledge_base_id'] or c['chunk_index']!=draft.chunk_index or c['metadata']!=draft.metadata:
                raise ValueError('Chunk drift; re-annotate after re-chunking')
            rebuilt.append(cid)
    if set(rebuilt)!=set(chunks):
        raise ValueError('Orphan chunk')
    ids, questions, groups = set(), set(), {'dev':set(), 'final':set()}
    for q in data['cases']:
        if q['id'] in ids:
            raise ValueError('Duplicate query ID')
        if q['question'] in questions:
            raise ValueError('Duplicate question')
        questions.add(q['question'])
        ids.add(q['id']); groups[q['split']].add(q['entity'])
        evidence = q['evidence']
        if q['answerable'] != bool(evidence) or set(q['relevant_chunk_ids'])!={v['chunk_id'] for v in evidence} or set(q['relevant_document_ids'])!={v['document_id'] for v in evidence}:
            raise ValueError('Relevance inconsistent')
        for v in evidence:
            c = chunks[v['chunk_id']]
            if not v['quote'] or v['quote'] not in c['content'] or c['document_id']!=v['document_id'] or any(c[k]!=q[k] for k in ('tenant_id','knowledge_base_id')):
                raise ValueError('Invalid evidence/scope')
        quotes = q['annotation']['required_quotes']
        if q['answerable'] and (not quotes or q['expected_answer']!=''.join(quotes)):
            raise ValueError('Answer not grounded in required quotes')
        expected = {c['id'] for c in chunks.values() if all(c[k]==q[k] for k in ('tenant_id','knowledge_base_id')) and any(quote in c['content'] for quote in quotes)}
        if expected != set(q['relevant_chunk_ids']):
            raise ValueError('Incomplete evidence labels')
        if not q['answerable'] and not q['annotation']['negative_reason']:
            raise ValueError('Negative rationale missing')
        if q['category']=='boundary':
            if not q['forbidden_document_ids'] or any(d not in docs or all(docs[d][k]==q[k] for k in ('tenant_id','knowledge_base_id')) for d in q['forbidden_document_ids']):
                raise ValueError('Boundary must refer to existing inaccessible documents')
    if groups['dev'] & groups['final']:
        raise ValueError('Entity split leakage')
    return dict(documents=len(docs), chunks=len(chunks), cases=len(ids), categories=dict(Counter(q['category'] for q in data['cases'])),
                splits=dict(Counter(q['split'] for q in data['cases'])), human_reviewed=0)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['generate','validate'])
    p.add_argument('--root', type=Path, default=DEFAULT)
    a = p.parse_args()
    print(json.dumps(generate(a.root) if a.action=='generate' else validate(a.root), ensure_ascii=False, indent=2))
