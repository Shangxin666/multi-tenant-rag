"""Record supplied content decisions separately; never approve exhaustive gold labels."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
SOURCE = ROOT / 'annotations/review-proposal.jsonl'
OUTPUT = ROOT / 'annotations/content-review-draft.jsonl'
RECHECK = ROOT / 'annotations/VUE011-evidence-recheck.json'
SUMMARY = ROOT / 'content-review-draft-summary.md'
VALIDATION = ROOT / 'content-review-draft-validation.json'

# This checks only existing VUE011/G2 labels, not all corpus relevance.
RECHECK_SPECS = [
    ('62e663f6-fd0c-559c-83e0-7c188ac39bb9', 198, 229, 'reactive_request_code',
     '同块说明 props.id 改变时重新 fetch，并展示 watchEffect 调用读取 toValue(url) 的 fetchData；不是独立的一次性异步请求。'),
    ('8e4f1aff-7937-55a2-8a64-90738891a3c4', 9, 42, 'reactive_request_code',
     'watch 监听 question 的变化，调用同块 getAnswer，并执行 fetch 后更新 answer；原来仅引用第 5 行的背景不充分，应以此具体链路替代引文。'),
    ('978727b4-5fcd-52c9-9986-cade596174c5', 379, 379, 'direct_normative_statement',
     '原文明示使用侦听器根据其他响应式状态的变更创建副作用，不仅是计算属性标题或禁止请求的背景；无需必须有代码才能成为直接事实依据。'),
    ('b7b4b10e-3228-5438-9b74-94acea8e14c9', 318, 333, 'reactive_request_code',
     '明确描述 todoId 变化时加载远程资源，并给出 watch(todoId, async ... fetch ...)；正标签依据不是前面的 once 示例。'),
    ('db2b988d-215d-57ec-bede-2f464494b832', 73, 95, 'reactive_request_code',
     'question 为 ref，watch(question, async ...) 在变化后 fetch 并更新响应式 answer；有完整源—回调—副作用链路。'),
    ('e6a99cf2-692a-571b-bba4-cc7b833242b0', 338, 349, 'reactive_request_code_and_statement',
     'watchEffect 内发起 fetch，原文明确 todoId.value 是依赖，每次变化时回调再次执行；不是只含 await 的代码。'),
    ('eb733fbd-8a4c-595e-bebe-6f8c374b6aca', 371, 381, 'reactive_request_code',
     'watch(id, ...) 内使用 newId 发起 fetch；正标签依据是该直接示例，而非 watch/watchEffect 的比较标题。'),
]


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def source_excerpt(doc, first, last, parsed):
    text = parsed[doc['id']]['sections'][0]['text']
    lines = text.splitlines(keepends=True)
    quote = ''.join(lines[first - 1:last]).rstrip('\n')
    start = sum(map(len, lines[:first - 1]))
    headings = [h for h in parsed[doc['id']]['headings'] if h['line'] <= first]
    return quote, {'source_path': doc['source_path'], 'line_start': first, 'line_end': last,
                   'char_start': start, 'char_end': start + len(quote),
                   'section': headings[-1] if headings else None,
                   'source_url': doc['source_url'] + f'#L{first}-L{last}'}


def main():
    for path in (OUTPUT, RECHECK, SUMMARY, VALIDATION):
        if path.exists():
            raise SystemExit('Refusing to overwrite existing content-review draft: ' + path.name)
    # Protect every file existing before this separate draft, including both old candidates.
    protected = {str(p.relative_to(REPO)).replace('\\', '/'): sha(p)
                 for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    historical = load(ROOT / 'manifest.json')['historical_v2_hashes']
    protected.update(historical)
    protected['scripts/evaluation/metrics.py'] = sha(REPO / 'scripts/evaluation/metrics.py')
    source_hash = sha(SOURCE)
    source = [json.loads(line) for line in SOURCE.read_text(encoding='utf-8').splitlines()]
    data = load(ROOT / 'dataset.json')
    docs = {d['id']: d for d in data['documents']}
    chunks = {c['id']: c for c in data['chunks']}
    parsed = {p['document_id']: p for p in map(json.loads, (ROOT / 'parsed.jsonl').read_text(encoding='utf-8').splitlines())}
    records = deepcopy(source)
    old_by_id = {q['id']: q for q in source}
    by_id = {q['id']: q for q in records}
    decisions = []
    for cid, first, last, support_type, reason in RECHECK_SPECS:
        c = chunks[cid]
        quote, location = source_excerpt(docs[c['document_id']], first, last, parsed)
        assert c['char_start'] <= location['char_start'] and location['char_end'] <= c['char_end']
        assert quote in c['content']
        decisions.append({'chunk_id': cid, 'source_path': c['source_path'], 'chunk_index': c['chunk_index'],
                          'fact_id': 'G2', 'disposition': 'retain_direct_support', 'support_type': support_type,
                          'reason': reason, 'quote': quote, 'location': location,
                          'review_scope': 'existing VUE011/G2 association only; not corpus-wide exhaustiveness'})
    for q in records:
        deferred = q['id'] == 'VUE026'
        q['content_review_draft_version'] = 'content-review-draft-0.1'
        q['assistant_content_review_passed'] = not deferred
        q['assistant_content_review_basis'] = 'User-supplied content-review decisions, applied by assistant; scoped clarifications and existing-label check recorded separately.'
        q['human_reviewed'] = False
        q['review_status'] = 'unverified'
        q['relevance_complete'] = False
        q['relevance_exhaustiveness_verified'] = False
        q['eligible_for_trusted_evaluation'] = False
        q['content_review_audit'] = {
            'source_file': 'annotations/review-proposal.jsonl', 'source_sha256': source_hash,
            'review_context_date': '2026-10-25',
            'scope': 'question/answer content; not human gold certification or exhaustive corpus relevance',
            'original_category': q['category'], 'changes': [],
            'positive_label_expansion_allowed': False,
        }
        if deferred:
            q['content_review_audit']['decision'] = 'deferred_missing_history_evidence'
            q['content_review_audit']['changes'].append('保留历史缺证组及暂缓计分状态，不补入外部证据。')
        elif q['id'] in ('VUE029', 'VUE030'):
            q['content_review_audit']['decision'] = 'content_passed_with_draft_clarification'
        elif q['id'] == 'VUE011':
            q['content_review_audit']['decision'] = 'answer_content_passed_existing_G2_labels_rechecked'
        elif not q['answerable']:
            q['content_review_audit']['decision'] = 'negative_content_retained'
        else:
            q['content_review_audit']['decision'] = 'content_passed'
    by_id['VUE004']['category'] = 'multi_fact_async_boundary'
    by_id['VUE004']['content_review_audit']['changes'].append('分类从 exact 调整为 multi_fact_async_boundary；答案和证据组不变。')

    # Strengthen the quote for an already-related chunk; do not add any positive label.
    q = by_id['VUE011']
    e = next(e for e in q['evidence'] if e['id'] == 'VUE011-R02')
    before = deepcopy(e)
    checked = next(d for d in decisions if d['chunk_id'] == '8e4f1aff-7937-55a2-8a64-90738891a3c4')
    e['quote'], e['location'] = checked['quote'], checked['location']
    q['evidence_quotes'] = [e['quote'] for e in q['evidence']]
    q['evidence_locations'] = [e['location'] for e in q['evidence']]
    q['content_review_audit']['changes'].append('G2 七个既有 Chunk 均有直接事实支持，未删除或降级；R02 原先仅引用背景句，改为同块第 9～42 行的 watch→getAnswer→fetch 直接链路。')
    q['content_review_audit']['evidence_revision'] = {'evidence_id': e['id'], 'before': before,
                                                    'after_quote': e['quote'], 'after_location': e['location']}
    q['existing_G2_evidence_recheck'] = {'artifact': 'annotations/VUE011-evidence-recheck.json',
                                        'existing_labels_checked': 7, 'removed_chunk_ids': [],
                                        'downgraded_group_associations': [], 'new_positive_chunk_ids': [],
                                        'relevance_exhaustiveness_verified': False}

    q = by_id['VUE029']
    q['expected_answer'] = '数字形式的 deep 表示 Vue 遍历响应式对象嵌套属性时的最大遍历深度，不是触发次数。文档明确该形式属于 Vue 3.5+；不能把 deep: 2 当作 Vue 3.4 已支持的最大深度配置。'
    q['rubric'] = ['明确数字 deep 控制最大遍历深度', '明确数字形式的 Vue 3.5+ 条件', '不把该语义直接用于 Vue 3.4，不解释成触发次数']
    q['answer_rubric'] = deepcopy(q['rubric'])
    q['content_review_audit']['changes'].append('明确最大遍历深度及 3.5+；保留既有相关 Chunk 和证据组。')

    q = by_id['VUE030']
    q['question'] = 'Vue 3.5 里我先 await 再调用 onWatcherCleanup 注册取消旧请求的回调，为什么不对？注册回调和真正取消请求是同一时刻吗？它和回调参数给的 onCleanup 限制一样吗？'
    q['expected_answer'] = 'onWatcherCleanup 仅在 Vue 3.5+ 支持，注册调用必须位于 watch/watchEffect 的同步执行阶段，不能放在 await 之后。注册清理回调不等于当场执行取消动作；在侦听器即将重新运行前，所注册的清理回调才执行取消旧请求等动作。回调参数形式的 onCleanup 与侦听器实例绑定，不受 onWatcherCleanup 的上述同步注册限制。'
    q['rubric'] = ['明确 Vue 3.5+ 条件', '区分同步阶段注册清理回调与稍后执行清理动作', '说明侦听器重新运行前执行已注册回调，注册本身不立即取消请求', '区分回调参数 onCleanup 的绑定关系与同步限制']
    q['answer_rubric'] = deepcopy(q['rubric'])
    timing = next(e for e in q['evidence'] if e['id'] == 'VUE030-R02')
    timing['supports_fact_ids'].append('G4')
    q['evidence_groups'].append({'id': 'G4', 'role': 'necessary',
                                 'fact': '清理回调在侦听器即将重新运行前执行；注册回调与执行取消动作不是同一时机',
                                 'alternative_evidence_ids': [timing['id']], 'supporting_chunk_ids': timing['chunk_ids'],
                                 'coverage_rule': 'any supporting chunk covers this atomic fact; one chunk may cover multiple groups',
                                 'status': 'mapped_unverified'})
    q['content_review_audit']['changes'].append('明确注册与清理动作执行的时机；G4 复用既有 R02 和既有 Chunk，不新增正标签。')

    errors = []
    for q in records:
        old = old_by_id[q['id']]
        if set(q['relevant_chunk_ids']) != set(old['relevant_chunk_ids']):
            errors.append(q['id'] + ': positive label set changed')
        if not (q['review_status'] == 'unverified' and q['human_reviewed'] is False
                and q['eligible_for_trusted_evaluation'] is False
                and q['relevance_exhaustiveness_verified'] is False and q['relevance_complete'] is False):
            errors.append(q['id'] + ': scope/review flags invalid')
        if q['assistant_content_review_passed'] != (q['id'] != 'VUE026'):
            errors.append(q['id'] + ': invalid content decision')
        if q['id'] not in ('VUE011', 'VUE030') and q['evidence_groups'] != old['evidence_groups']:
            errors.append(q['id'] + ': unrequested group change')
        seen = set()
        for e in q['evidence']:
            loc = e['location']
            key = (e['document_id'], loc['char_start'], loc['char_end'])
            if key in seen:
                errors.append(q['id'] + ': duplicate evidence location')
            seen.add(key)
            text = parsed[e['document_id']]['sections'][0]['text']
            if text[loc['char_start']:loc['char_end']] != e['quote']:
                errors.append(q['id'] + ': quote position invalid')
            for cid in e['chunk_ids']:
                c = chunks.get(cid)
                if c is None or c['document_id'] != e['document_id'] or not (
                    c['char_start'] <= loc['char_start'] and loc['char_end'] <= c['char_end']
                    and e['quote'] in c['content'] and all(c[k] == q[k] for k in ('tenant_id', 'knowledge_base_id'))):
                    errors.append(q['id'] + ': invalid chunk/source/scope')
        for g in q['evidence_groups']:
            evidence = [e for e in q['evidence'] if g['id'] in e['supports_fact_ids']]
            if {e['id'] for e in evidence} != set(g['alternative_evidence_ids']):
                errors.append(q['id'] + ': inconsistent group evidence')
            if {cid for e in evidence for cid in e['chunk_ids']} != set(g['supporting_chunk_ids']):
                errors.append(q['id'] + ': inconsistent group chunks')
            if not g['supporting_chunk_ids'] and not (q['id'] == 'VUE026' and g['id'] == 'G1'):
                errors.append(q['id'] + ': undeclared missing evidence group')
        if q['id'] in ('VUE021', 'VUE022', 'VUE023', 'VUE024', 'VUE025'):
            if q['negative_type'] != old['negative_type'] or q['relevant_chunk_ids'] or q['answerable']:
                errors.append(q['id'] + ': negative classification or empty set changed')
    if by_id['VUE026']['evidence_groups'] != old_by_id['VUE026']['evidence_groups'] or by_id['VUE026']['eligible_after_human_review']:
        errors.append('VUE026: deferred evidence state changed')
    changed = [name for name, expected in protected.items() if sha(REPO / name) != expected]
    if changed:
        errors.append('Protected files changed')
    if errors:
        raise ValueError(errors)

    recheck = {'case_id': 'VUE011', 'source_proposal_sha256': source_hash,
               'review_scope': 'all seven previously marked G2 chunks; no search for additional positives',
               'results': decisions, 'chunk_ids_to_remove': [], 'chunk_ids_to_downgrade_from_G2': [],
               'new_positive_chunk_ids': [], 'citation_fix': 'VUE011-R02: line 5 -> lines 9-42 inside the same already-positive chunk',
               'relevance_exhaustiveness_verified': False}
    lines = ['# real-tech-v1 内容审核结果草案', '',
             '依据用户本轮 30 题内容审核结论生成。原始候选、修订候选及 v2 均保留不变。', '',
             '- assistant_content_review_passed=true：29 题；VUE026=false，仍暂缓计分。',
             '- 全部 human_reviewed=false、review_status=unverified；可信评测题数仍为 0。',
             '- 全部 relevance_exhaustiveness_verified=false、relevance_complete=false；内容通过不等于全语料正标签已穷尽。',
             '- 新增正标签 0、删除正标签 0、G2 Chunk 降级 0。', '',
             '## 逐项处理', '',
             '- VUE001～003、005～010、012～020、027～028：保留标准答案和证据组，记录内容通过。',
             '- VUE004：分类改为 multi_fact_async_boundary，标准答案及证据组不变。',
             '- VUE011：标准答案不变；逐块检查 G2 七块，全部有直接规则或响应式请求链路。',
             '  - computed#9 明确“根据其他响应式状态的变更来创建副作用”，是直接规范性依据，不强制必须给代码。',
             '  - watchers#0 原来只引用第 5 行背景；在本草案内改为第 9～42 行 watch→getAnswer→fetch，原修订候选不变。',
             '- VUE021～023：语料范围不足；VUE024：用户上下文不足；VUE025：测量依据不足。空相关集合及此前授权范围核查结论不变。',
             '- VUE026：缺失历史证据组原样保留，不补入外部发布说明。',
             '- VUE029：明确数字 deep 为最大遍历深度，版本条件为 Vue 3.5+。',
             '- VUE030：明确同步注册清理回调与随后执行取消动作不同；G4 仅复用已有关联 Chunk 和 R02。', '',
             '## 删除或降级清单', '',
             '需要删除的 Chunk ID：无。需要从 VUE011/G2 降级的 Chunk ID：无。',
             '这不表示全部标签已获人工确认，也不表示已经穷尽整个语料的相关证据。', '',
             '## VUE011/G2 逐块依据', '']
    for item in decisions:
        loc = item['location']
        lines += [f'- `{item["chunk_id"]}`：{item["reason"]}',
                  f'  - 来源：{loc["source_path"]}:{loc["line_start"]}–{loc["line_end"]}；保留直接支持。']
    lines += ['', '## VUE029 澄清后的答案', '', by_id['VUE029']['expected_answer'], '',
              '## VUE030 澄清后的答案', '', by_id['VUE030']['expected_answer'], '',
              '## 校验范围', '',
              '检查 30 题、空相关负样本、既有正标签集合不扩大、证据位置与组引用、暂缓组以及受保护文件哈希。',
              '不运行模型、不访问数据库、不改变任何指标公式；不声称完成语义标签穷尽性证明。']
    OUTPUT.write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in records), encoding='utf-8')
    RECHECK.write_text(json_text(recheck), encoding='utf-8')
    SUMMARY.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    report = {'status': 'passed_with_declared_deferral', 'records': len(records),
              'assistant_content_review_passed_true': 29, 'human_reviewed_true': 0,
              'trusted_evaluation_records': 0, 'relevance_exhaustiveness_verified_true': 0,
              'positive_labels_added': 0, 'positive_labels_removed': 0,
              'VUE011_G2_checked': 7, 'VUE011_G2_downgraded': 0,
              'declared_missing_groups': ['VUE026/G1'], 'errors': errors,
              'protected_files_changed': changed, 'protected_file_sha256': protected,
              'output_sha256': {str(p.relative_to(ROOT)): sha(p) for p in (OUTPUT, RECHECK, SUMMARY)},
              'models_run': False, 'database_accessed': False}
    VALIDATION.write_text(json_text(report), encoding='utf-8')
    print(json_text({k: v for k, v in report.items() if k not in ('protected_file_sha256', 'output_sha256')}))


if __name__ == '__main__':
    main()
