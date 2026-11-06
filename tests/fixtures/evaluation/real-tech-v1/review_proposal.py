"""Independent review proposal; immutable inputs, no models, DB or metric changes."""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
PROPOSAL = ROOT / 'annotations/review-proposal.jsonl'
SUMMARY = ROOT / 'review-proposal-summary.md'
VALIDATION = ROOT / 'review-proposal-validation.json'
ALIASES = {
    'RF': 'guide/essentials/reactivity-fundamentals.md',
    'C': 'guide/essentials/computed.md', 'W': 'guide/essentials/watchers.md',
    'L': 'guide/essentials/lifecycle.md', 'TF': 'guide/essentials/template-refs.md',
    'CB': 'guide/essentials/component-basics.md', 'P': 'guide/components/props.md',
    'EV': 'guide/components/events.md', 'VM': 'guide/components/v-model.md',
    'AT': 'guide/components/attrs.md', 'SL': 'guide/components/slots.md',
    'PI': 'guide/components/provide-inject.md', 'CO': 'guide/reusability/composables.md',
    'EX': 'guide/extras/reactivity-in-depth.md', 'API': 'api/reactivity-core.md',
}


def fact(description, *spans):
    return {'fact': description, 'spans': list(spans)}


# Each span supports the stated atomic fact; several facts may use one excerpt.
# The historical defineModel fact deliberately has no frozen-corpus evidence.
FACTS = {
    'VUE001': [fact('响应式状态修改后的 DOM 更新是缓冲、异步执行的', ('RF', 336, 336)),
               fact('修改状态后可等待 nextTick 再访问 DOM', ('RF', 338, 338), ('RF', 343, 349))],
    'VUE002': [fact('计算属性按响应式依赖缓存，依赖更新才重新计算', ('C', 173, 173)),
               fact('模板方法在重渲染时重新执行', ('C', 197, 197))],
    'VUE003': [fact('组件事件不冒泡，只能直接监听子组件事件', ('EV', 65, 65))],
    'VUE004': [fact('普通 setup 的异步回调中不能依赖当前实例注册生命周期钩子，应同步注册', ('L', 44, 44), ('L', 46, 53)),
               fact('允许在同步起源于 setup 的外部函数内注册', ('L', 55, 55)),
               fact('script setup 顶层 await 由编译器恢复实例，是特殊上下文，不能泛化为任意异步回调', ('CO', 308, 308))],
    'VUE005': [fact('多根节点不会自动透传 attributes，未显式绑定会警告', ('AT', 131, 137)),
               fact('可选择目标根节点显式绑定 $attrs', ('AT', 119, 126), ('AT', 145, 151))],
    'VUE006': [fact('直接传入对象的数字属性得到普通值，不能直接作为响应式源', ('W', 137, 145)),
               fact('应传入返回该属性的 getter', ('W', 148, 157), ('API', 439, 449))],
    'VUE007': [fact('响应式数组及 Map 中的 ref 元素不会自动解包', ('RF', 499, 499), ('API', 131, 131), ('API', 166, 166)),
               fact('访问这些 ref 元素需要 .value', ('RF', 501, 508), ('API', 165, 175))],
    'VUE008': [fact('多个祖先提供同名依赖时采用最近祖先的值', ('PI', 126, 126), ('PI', 174, 174))],
    'VUE009': [fact('script setup 组件默认私有，须用 defineExpose 显式暴露', ('TF', 191, 191)),
               fact('defineExpose 必须在 await 前调用', ('TF', 210, 210))],
    'VUE010': [fact('推荐返回普通非响应式对象，其中包含多个 ref，解构仍保留响应性', ('CO', 268, 268)),
               fact('解构返回的 reactive 对象可能断开属性的响应式连接，而 ref 保留连接', ('CO', 275, 275))],
    'VUE011': [fact('computed getter 只计算派生值，不执行请求、DOM 修改等副作用', ('C', 379, 379)),
               fact('响应式状态改变驱动的请求可放在 watch 或 watchEffect 中', ('C', 379, 379), ('W', 5, 5), ('W', 73, 95), ('W', 318, 333), ('W', 338, 349), ('W', 371, 381), ('CO', 205, 229))],
    'VUE012': [fact('prop 的顶层绑定不能由子组件重新赋值', ('P', 369, 377), ('P', 457, 457)),
               fact('普通可变对象或数组的嵌套内容可因共享引用被修改，影响父级状态', ('P', 457, 459)),
               fact('通常由子组件发事件通知父组件更新，避免隐式嵌套修改', ('P', 459, 459), ('CB', 363, 363), ('CB', 372, 384), ('CB', 384, 384), ('EV', 65, 82), ('EV', 78, 112))],
    'VUE013': [fact('已声明的 props 和 emits 监听器不属于透传 attributes', ('AT', 11, 11), ('AT', 72, 72), ('AT', 103, 103), ('CB', 422, 422), ('EV', 225, 225)),
               fact('click 在 emits 中声明后，监听组件发出的 click，不再自动响应原生 click', ('EV', 225, 225))],
    'VUE014': [fact('模板引用在挂载后才可访问，初次渲染或元素移除时可能为空', ('TF', 96, 96), ('TF', 100, 108)),
               fact('DOM 相关副作用可安排在 onMounted 等挂载后阶段', ('CO', 293, 293), ('CO', 36, 37), ('CO', 100, 101)),
               fact('手动添加的事件监听器需要在组件卸载时配对移除，ref 变空不等于监听器已清理', ('CO', 295, 295), ('CO', 36, 37), ('CO', 100, 101))],
    'VUE015': [fact('原始类型属性被解构为局部变量后不再触发源代理访问，因而断开连接', ('EX', 107, 107), ('RF', 448, 461)),
               fact('从普通对象解构得到的 ref 保留自身响应性', ('CO', 268, 268), ('CO', 275, 275))],
    'VUE016': [fact('watch 仅追踪显式数据源，不追踪回调内的其它访问', ('W', 363, 363)),
               fact('watchEffect 自动追踪同步执行中访问的响应式依赖', ('W', 365, 365)),
               fact('异步 watchEffect 仅追踪第一个 await 前访问的依赖', ('W', 356, 356))],
    'VUE017': [fact('深层 reactive 对象属性中的 ref 自动解包', ('RF', 470, 470), ('RF', 495, 495), ('API', 129, 129), ('API', 178, 187)),
               fact('响应式数组或 Map 的 ref 元素不会自动解包', ('RF', 499, 499), ('API', 131, 131), ('API', 166, 166)),
               fact('响应式数组或 Map 中的 ref 元素使用 .value 读取', ('RF', 501, 508), ('API', 165, 175))],
    'VUE018': [fact('插槽表达式使用定义它的父级作用域，不能直接读子组件状态', ('SL', 101, 103)),
               fact('子组件向 slot 传递属性，父组件通过 v-slot 接收插槽 props', ('SL', 351, 353), ('SL', 388, 390), ('SL', 408, 413))],
    'VUE019': [fact('reactive 产生代理对象，代理与原对象不是同一身份', ('RF', 399, 406), ('API', 135, 135), ('EX', 109, 109), ('RF', 64, 64)),
               fact('应统一通过代理访问和修改，以被响应式系统追踪', ('RF', 409, 409), ('API', 135, 135), ('RF', 64, 64))],
    'VUE020': [fact('默认无参数组件 v-model 对应 modelValue prop 和 update:modelValue 事件', ('VM', 59, 60), ('VM', 151, 152), ('VM', 185, 193), ('VM', 265, 265)),
               fact('子组件读取 prop，并通过事件把新值交给父组件更新', ('VM', 59, 60), ('VM', 78, 84), ('VM', 151, 152), ('VM', 185, 193)),
               fact('具名 v-model:title 对应 title prop 和 update:title 事件', ('VM', 265, 265))],
    'VUE026': [fact('defineModel 在 3.3 中为需显式启用的实验特性，3.4 转为稳定；当前冻结语料缺此历史证据'),
               fact('当前指南从 Vue 3.4 开始推荐 defineModel', ('VM', 13, 13)),
               fact('不使用宏时，默认组件 v-model 使用 modelValue 和 update:modelValue', ('VM', 59, 60), ('VM', 151, 152))],
    'VUE027': [fact('默认编译配置下，3.4 及以下的此类解构变量不随 prop 更新', ('P', 138, 138)),
               fact('3.5+ 在同一 script setup 内将解构变量访问转换为 props 属性访问', ('P', 138, 138))],
    'VUE028': [fact('useTemplateRef 是 Vue 3.5+ API，旧版本尚未引入', ('TF', 15, 15), ('TF', 39, 39)),
               fact('旧写法声明与模板 ref attribute 匹配的 ref', ('TF', 39, 48)),
               fact('模板引用需在挂载后访问', ('TF', 96, 96))],
    'VUE029': [fact('数字 deep 表示最大遍历深度，属于 Vue 3.5+ 语义，不能直接保证 3.4 支持', ('W', 227, 227), ('API', 426, 426))],
    'VUE030': [fact('onWatcherCleanup 属于 Vue 3.5+ 功能', ('W', 449, 449), ('API', 557, 559), ('API', 317, 328), ('API', 540, 549)),
               fact('onWatcherCleanup 必须在同步执行期间注册，不能在 await 后调用', ('W', 449, 449), ('API', 557, 559)),
               fact('回调参数 onCleanup 与侦听器绑定，不受上述同步调用限制', ('W', 489, 489))],
}

OVERRIDES = {
    'VUE004': {
        'question': '在普通 setup() 中，我把 onMounted 注册放进接口 Promise.then 回调或 setTimeout 回调里，这样为什么不行？它与 script setup 中顶层 await 后调用组合式 API 的情况有什么区别？',
        'expected_answer': '普通 setup 的异步回调不会保留当前组件实例，应在初始化的同步调用链中注册生命周期钩子。注册可以位于同步起源于 setup 的外部函数。script setup 的顶层 await 是编译器会恢复当前实例的特殊上下文，不能据此认为任意 Promise 或定时器回调都可注册钩子。',
        'rubric': ['限定普通 setup 的 Promise/定时器异步回调场景', '说明同步注册及同步外部调用链', '明确 script setup 顶层 await 的编译器恢复实例例外，不泛化为任意异步回调'],
    },
    'VUE012': {
        'question': "父组件把一个普通的可变 user 对象作为 prop 传给编辑器。子组件直接执行 props.user.name = '新名字'，和执行 props.user = 新对象有什么区别？推荐怎样把姓名修改交给父组件处理？",
        'expected_answer': 'prop 绑定是只读的，子组件不能重新赋值 props.user。但父组件传入普通可变对象时，子组件通常可以修改其嵌套属性；这是共享对象引用带来的修改，也会影响父组件持有的对象。通常应避免这种隐式修改，由子组件发出变更事件，父组件监听后更新自己的状态；紧密耦合场景需明确约定。',
        'rubric': ['区分重新赋值 prop 绑定与修改嵌套属性', '解释共享对象引用带来的父级状态影响', '不把 props 描述成对任意嵌套内容都强制深只读', '给出子组件通知、父组件更新的推荐数据流'],
    },
    'VUE014': {
        'question': '我想在 useFocus 中，等组件挂载后通过模板 ref 聚焦 input，并手动给 window 注册一个事件监听器。模板 ref 初始为空应该怎样处理？组件卸载时，手动注册的监听器应该在哪里移除？',
        'expected_answer': '模板引用需要等挂载后访问，尚未挂载或元素被移除时可能为空，使用前应检查。模板引用的可用性由 Vue 渲染生命周期管理；它与手动注册的事件监听器不是同一资源。手动注册的 window 监听器应在 onUnmounted 中用相应的 removeEventListener 清理，不能认为 ref 变空就意味着监听器已移除。',
        'rubric': ['挂载后访问引用，并处理空值', '区分模板引用与手动注册的监听器', '注册与移除使用对应的事件、目标和回调', '不把元素消失与组件卸载混为同一时机'],
    },
    'VUE020': {
        'question': '在自定义组件上使用不带参数的 v-model="value" 时，不用 defineModel 应该怎样实现？子组件接收哪个 prop、触发哪个事件？这和 v-model:title 有什么区别？',
        'expected_answer': '默认无参数的组件 v-model 对应 modelValue prop 和 update:modelValue 事件。子组件读取 prop，在需要更新时通过该事件把新值交给父组件。具名的 v-model:title 则对应 title 和 update:title，不能混用默认名称。',
        'rubric': ['明确讨论的是组件上的默认无参数 v-model', '正确给出 modelValue/update:modelValue', '说明父级值通过事件更新', '区分 title/update:title；不混入原生 input 的展开协议'],
    },
    'VUE026': {
        'question': '同事说 defineModel 在 Vue 3.3 就能用，文档却从 3.4 开始推荐。这里的实验性支持和正式稳定有什么区别？如果 Vue 3.3 项目不启用实验特性，默认无参数的组件 v-model 应怎样实现？',
        'expected_answer': 'defineModel 在 Vue 3.3 中已作为需要显式启用的实验性功能提供，3.4 转为稳定功能并被文档推荐。不能说它到 3.4 才首次存在。不启用实验宏时，可用 modelValue prop 和 update:modelValue 事件实现默认组件 v-model。',
        'rubric': ['不把 3.4 开始推荐解释成 3.3 完全不存在', '区分 3.3 实验性且显式启用与 3.4 稳定', '给出默认无参数协议', '不编造未核对版本的构建配置'],
    },
}

NEGATIVE_TYPES = {
    'VUE021': 'corpus_scope_insufficient', 'VUE022': 'corpus_scope_insufficient',
    'VUE023': 'corpus_scope_insufficient', 'VUE024': 'user_context_insufficient',
    'VUE025': 'measurement_evidence_insufficient',
}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context():
    data = load(ROOT / 'dataset.json')
    original = [json.loads(line) for line in (ROOT / 'annotations/candidates.jsonl').read_text(encoding='utf-8').splitlines()]
    assert data['cases'] == original
    return data, {d['id']: d for d in data['documents']}, {c['id']: c for c in data['chunks']}


def protected_hashes():
    manifest = load(ROOT / 'manifest.json')
    paths = {ROOT / p for p in manifest['files']} | {ROOT / 'manifest.json', ROOT / 'validation.json'}
    paths |= {REPO / p for p in manifest['historical_v2_hashes']}
    paths |= {REPO / 'scripts/evaluation/metrics.py'}
    return {str(p.relative_to(REPO)).replace('\\', '/'): sha(p) for p in sorted(paths)}


def make_records():
    data, docs, chunks = context()
    parsed = {row['document_id']: row for row in map(json.loads, (ROOT / 'parsed.jsonl').read_text(encoding='utf-8').splitlines())}
    by_path = {d['source_path']: d for d in docs.values()}
    result = []
    for old in data['cases']:
        q = deepcopy(old)
        q.update(deepcopy(OVERRIDES.get(q['id'], {})))
        q['rubric'] = q.get('rubric', deepcopy(old['answer_rubric']))
        q['answer_rubric'] = deepcopy(q['rubric'])
        q['proposal_version'] = 'review-proposal-0.1'
        q['source_dataset_sha256'] = sha(ROOT / 'dataset.json')
        q['review_status'], q['human_reviewed'] = 'unverified', False
        q['eligible_for_trusted_evaluation'] = False
        deferred = q['id'] == 'VUE026'
        q['eligible_after_human_review'] = not deferred
        q['scoring_disposition'] = 'deferred_missing_corpus_evidence' if deferred else 'blocked_pending_human_review'
        q['trusted_evaluation_exclusion_reasons'] = ['unverified'] + (['missing_historical_version_evidence'] if deferred else [])
        q['negative_type'] = NEGATIVE_TYPES.get(q['id'])
        q['evidence'], q['evidence_groups'] = [], []
        evidence_by_location = {}
        for n, group_spec in enumerate(FACTS.get(q['id'], []), 1):
            gid = f'G{n}'
            alternatives = []
            for alias, first, last in group_spec['spans']:
                path = 'src/' + ALIASES[alias]
                doc = by_path[path]
                text = parsed[doc['id']]['sections'][0]['text']
                lines = text.splitlines(keepends=True)
                excerpt = ''.join(lines[first - 1:last]).rstrip('\n')
                start = sum(len(line) for line in lines[:first - 1])
                end = start + len(excerpt)
                matching = [c for c in chunks.values() if c['document_id'] == doc['id']
                            and c['char_start'] <= start and end <= c['char_end']
                            and excerpt in c['content']]
                if not matching:
                    raise ValueError(f'{q["id"]} {gid} {alias}:{first}-{last} crosses a chunk; choose an atomic excerpt')
                key = (doc['id'], start, end)
                if key not in evidence_by_location:
                    eid = f'{q["id"]}-R{len(q["evidence"]) + 1:02d}'
                    sections = [h for h in parsed[doc['id']]['headings'] if h['line'] <= first]
                    e = {'id': eid, 'document_id': doc['id'], 'quote': excerpt,
                         'supports_fact_ids': [], 'role': 'direct_support_candidate',
                         'chunk_ids': [c['id'] for c in matching],
                         'location': {'source_path': path, 'line_start': first, 'line_end': last,
                                      'char_start': start, 'char_end': end,
                                      'section': sections[-1] if sections else None,
                                      'source_url': doc['source_url'] + f'#L{first}-L{last}'},
                         'mapping_method': 'source position containment AND exact quote containment; no cross-occurrence matching'}
                    q['evidence'].append(e)
                    evidence_by_location[key] = e
                e = evidence_by_location[key]
                if gid not in e['supports_fact_ids']:
                    e['supports_fact_ids'].append(gid)
                if e['id'] not in alternatives:
                    alternatives.append(e['id'])
            support = sorted({cid for e in q['evidence'] if gid in e['supports_fact_ids'] for cid in e['chunk_ids']})
            q['evidence_groups'].append({'id': gid, 'role': 'necessary', 'fact': group_spec['fact'],
                                         'alternative_evidence_ids': alternatives, 'supporting_chunk_ids': support,
                                         'coverage_rule': 'any supporting chunk covers this atomic fact; one chunk may cover multiple groups',
                                         'status': 'missing_corpus_evidence' if not support else 'mapped_unverified'})
        relevant = sorted({cid for e in q['evidence'] for cid in e['chunk_ids']})
        q['relevant_chunk_ids'] = relevant
        q['relevant_document_ids'] = sorted({chunks[cid]['document_id'] for cid in relevant})
        q['source_document_ids'] = deepcopy(q['relevant_document_ids'])
        q['evidence_quotes'] = [e['quote'] for e in q['evidence']]
        q['evidence_locations'] = [e['location'] for e in q['evidence']]
        q['relevance_complete'] = False
        q['requires_multiple_documents'] = False
        q['reasoning_type'] = 'multi_fact' if len(q['evidence_groups']) > 1 else ('negative' if not q['answerable'] else 'single_fact')
        q['negative_reason_original'] = old['negative_reason']
        if q['negative_type']:
            q['negative_reason'] = q['negative_type']
            q['negative_review']['proposal_scope_conclusion'] = 'Insufficient evidence for the requested answer in the frozen authorized corpus; still unverified.'
            q['negative_review']['literal_search_is_not_absence_proof'] = True
        added = sorted(set(relevant) - set(old['relevant_chunk_ids']))
        removed = sorted(set(old['relevant_chunk_ids']) - set(relevant))
        q['review_notes'] = {
            'basis': 'User-confirmed partial direct relevance, alternative evidence, multi-fact grouping rules; AI-assisted revision only.',
            'wording_changed': any(q[k] != old.get(k) for k in ('question', 'expected_answer')),
            'original_relevant_chunk_ids': old['relevant_chunk_ids'],
            'added_chunks': [{'chunk_id': cid, 'source_path': docs[chunks[cid]['document_id']]['source_path'],
                              'chunk_index': chunks[cid]['chunk_index'],
                              'supports': [{'fact_id': g['id'], 'fact': g['fact'],
                                            'evidence_ids': [e['id'] for e in q['evidence'] if cid in e['chunk_ids'] and g['id'] in e['supports_fact_ids']]}
                                           for g in q['evidence_groups'] if cid in g['supporting_chunk_ids']]}
                             for cid in added],
            'removed_chunk_ids': removed,
            'regrouped_by_necessary_fact': bool(q['answerable']),
            'background_evidence_promoted': False,
            'metric_formulas_changed': False,
            'human_review_required': True,
        }
        if q['negative_type']:
            q['review_notes']['negative_recheck'] = {
                'reason_type': q['negative_type'],
                'scope': 'all frozen 15 documents / 215 chunks; linked external pages are not corpus evidence',
                'conclusion': 'No sufficient evidence for the requested specific answer; generic related facts do not make it answerable.',
                'caveat': 'Literal URL/base64 matches (including original TTL matches) are not substantive configuration evidence; human adjudication remains pending.',
            }
        if q['id'] == 'VUE008':
            q['review_notes']['location_correction'] = 'Line 126 maps only to PI#3; separate line 174 evidence maps to PI#4 and PI#5. Same wording does not imply same source occurrence.'
        if q['id'] in ('VUE011', 'VUE012', 'VUE013', 'VUE014', 'VUE015'):
            q['review_notes']['category_interpretation'] = 'multi_evidence means multiple necessary facts, not mandatory multiple source documents'
        if deferred:
            q['review_notes']['pending_extension'] = 'Historical experimental/stable status is not evidenced by the frozen 215 chunks; no external release notes added to gold.'
        q['annotation_notes'] = '审核修订候选；按必要事实分组并修正原文位置；仍未完成人工逐证据验收，不进入可信评测。'
        result.append(q)
    return result


def validate(records, protected):
    data, docs, chunks = context()
    errors = []
    expected_missing, unexpected_missing = [], []
    duplicate_evidence, bad_ids, bad_positions, orphan_groups = [], [], [], []
    def require(condition, message):
        if not condition:
            errors.append(message)
    require(len(records) == 30 and {q['id'] for q in records} == {q['id'] for q in data['cases']}, 'Case IDs/count mismatch')
    for q in records:
        require(all(k in q for k in ('question', 'expected_answer', 'rubric', 'relevant_chunk_ids', 'evidence_groups', 'review_notes')), q['id'] + ': required field absent')
        require(q['review_status'] == 'unverified' and not q['human_reviewed'] and not q['eligible_for_trusted_evaluation'], q['id'] + ': invalid review state')
        require(q['rubric'] == q['answer_rubric'] and bool(q['rubric']), q['id'] + ': invalid rubric')
        require(len(q['relevant_chunk_ids']) == len(set(q['relevant_chunk_ids'])), q['id'] + ': duplicate relevant ID')
        gids = [g['id'] for g in q['evidence_groups']]
        eids = [e['id'] for e in q['evidence']]
        expected_groups = FACTS.get(q['id'], [])
        require(gids == [f'G{i}' for i in range(1, len(expected_groups) + 1)], q['id'] + ': necessary fact group missing or reordered')
        require([g['fact'] for g in q['evidence_groups']] == [g['fact'] for g in expected_groups], q['id'] + ': necessary fact definition drift')
        require(len(gids) == len(set(gids)) and len(eids) == len(set(eids)), q['id'] + ': duplicate group/evidence ID')
        seen = set()
        for e in q['evidence']:
            loc = e['location']
            key = (e['document_id'], loc['char_start'], loc['char_end'])
            if key in seen:
                duplicate_evidence.append([q['id'], e['id']])
            seen.add(key)
            doc = docs.get(e['document_id'])
            require(doc is not None, q['id'] + ': invalid document')
            if doc is None:
                continue
            text = (ROOT / doc['path']).read_text(encoding='utf-8-sig')
            if text[loc['char_start']:loc['char_end']] != e['quote']:
                bad_positions.append([q['id'], e['id'], 'quote offsets'])
            require(e['quote'] == '\n'.join(text.splitlines()[loc['line_start'] - 1:loc['line_end']]).rstrip('\n'), q['id'] + ': line quote mismatch')
            require(loc['source_path'] == doc['source_path'], q['id'] + ': source path mismatch')
            require(loc['source_url'] == doc['source_url'] + f'#L{loc["line_start"]}-L{loc["line_end"]}', q['id'] + ': source URL mismatch')
            require(loc['line_start'] == text.count('\n', 0, loc['char_start']) + 1, q['id'] + ': source line mismatch')
            require(bool(e['supports_fact_ids']) and set(e['supports_fact_ids']) <= set(gids), q['id'] + ': missing fact reference')
            for cid in e['chunk_ids']:
                c = chunks.get(cid)
                if c is None:
                    bad_ids.append([q['id'], cid])
                    continue
                if not (c['document_id'] == e['document_id'] and e['quote'] in c['content']
                        and c['char_start'] <= loc['char_start'] and loc['char_end'] <= c['char_end']):
                    bad_positions.append([q['id'], e['id'], cid])
                require(all(c[k] == q[k] for k in ('tenant_id', 'knowledge_base_id')), q['id'] + ': out-of-scope evidence')
        for cid in q['relevant_chunk_ids']:
            if cid not in chunks:
                bad_ids.append([q['id'], cid])
        require(set(q['relevant_chunk_ids']) == {cid for e in q['evidence'] for cid in e['chunk_ids']}, q['id'] + ': relevance union mismatch')
        for g in q['evidence_groups']:
            support = {cid for e in q['evidence'] if g['id'] in e['supports_fact_ids'] for cid in e['chunk_ids']}
            require(support == set(g['supporting_chunk_ids']), q['id'] + ': group chunk union mismatch')
            expected_eids = {e['id'] for e in q['evidence'] if g['id'] in e['supports_fact_ids']}
            if set(g['alternative_evidence_ids']) != expected_eids:
                orphan_groups.append([q['id'], g['id']])
            if not support:
                (expected_missing if q['id'] == 'VUE026' and g['id'] == 'G1' and not q['eligible_after_human_review'] else unexpected_missing).append([q['id'], g['id'], g['fact']])
        require(bool(q['evidence_groups']) == q['answerable'], q['id'] + ': answerable/group mismatch')
        if not q['answerable']:
            require(not q['evidence'] and not q['relevant_chunk_ids'] and q['negative_type'] in NEGATIVE_TYPES.values(), q['id'] + ': invalid negative')
        require(all(item['supports'] for item in q['review_notes']['added_chunks']), q['id'] + ': added chunk lacks fact explanation')
        require({x['chunk_id'] for x in q['review_notes']['added_chunks']} == set(q['relevant_chunk_ids']) - set(q['review_notes']['original_relevant_chunk_ids']), q['id'] + ': incomplete added-chunk audit')
        require(set(q['review_notes']['removed_chunk_ids']) == set(q['review_notes']['original_relevant_chunk_ids']) - set(q['relevant_chunk_ids']), q['id'] + ': incomplete removal audit')
        for item in q['review_notes']['added_chunks']:
            expected_facts = {g['id'] for g in q['evidence_groups'] if item['chunk_id'] in g['supporting_chunk_ids']}
            require({s['fact_id'] for s in item['supports']} == expected_facts, q['id'] + ': added-chunk fact mapping mismatch')
    unchanged = all((REPO / name).exists() and sha(REPO / name) == expected for name, expected in protected.items())
    require(unchanged, 'Protected input/history/metric files changed')
    require(expected_missing and len(expected_missing) == 1, 'Expected VUE026 missing fact declaration not preserved')
    passed = not any((errors, duplicate_evidence, bad_ids, bad_positions, orphan_groups, unexpected_missing))
    return {'status': 'passed_with_declared_deferral' if passed else 'failed', 'structural_validation_passed': passed,
            'scope': 'ID, source-position, schema, fact-reference and immutability checks; not human semantic approval',
            'records': len(records), 'all_unverified': all(q['review_status'] == 'unverified' for q in records),
            'human_reviewed_true': sum(q['human_reviewed'] for q in records), 'trusted_evaluation_records': 0,
            'reviewable_after_human_approval': sum(q['eligible_after_human_review'] for q in records),
            'invalid_chunk_ids': bad_ids, 'duplicate_evidence': duplicate_evidence,
            'invalid_evidence_positions': bad_positions, 'orphan_or_inconsistent_groups': orphan_groups,
            'unexpected_missing_groups': unexpected_missing, 'declared_missing_groups': expected_missing,
            'errors': errors, 'protected_files_unchanged': unchanged,
            'protected_input_hashes': protected, 'models_loaded': False, 'database_accessed': False}


def summary(records, validation):
    lines = ['# real-tech-v1 审核修订候选差异', '',
             '30 题全部 unverified / human_reviewed=false；不覆盖原始候选，不运行模型或数据库。',
             '29 题仅具备后续人工验收资格；VUE026 因冻结语料缺历史证据继续暂不计分。当前可信评测题数仍为 0。', '',
             '## 规则', '',
             '支持至少一个明确必要事实点可标相关；背景、标题和同词命中不升级。',
             '同一事实的证据互为替代，一个 Chunk 可以覆盖多组，多事实点不要求多个文档。',
             '保留原 Recall/MRR/nDCG 代码；没有实现或执行新指标。未来 Evidence Group Coverage 可按必要组中任一支持 Chunk 命中计算。', '',
             '## 变更统计', '',
             f'- 新增题目—Chunk 关联：{sum(len(q["review_notes"]["added_chunks"]) for q in records)}。',
             f'- 移除题目—Chunk 关联：{sum(len(q["review_notes"]["removed_chunk_ids"]) for q in records)}。',
             f'- 必要事实组：{sum(len(q["evidence_groups"]) for q in records)}；明确待扩展缺证组：1（VUE026/G1）。',
             '- VUE004、VUE012、VUE014、VUE020 调整精确表述；VUE026 使用历史区别草案并暂缓。',
             '- VUE008 分开记录 126 行和 174 行的重复原句，按真实位置映射。',
             '- VUE011～VUE015 重组必要事实点，保留原 category 但不强制多文档。',
             '- 负样本分类：VUE021～023 语料范围不足；VUE024 用户上下文不足；VUE025 测量依据不足。', '',
             '## 逐题差异', '', '| 题目 | 新增关联 | 移除关联 | 必要组 | 处理 |', '| --- | ---: | ---: | ---: | --- |']
    for q in records:
        n = q['review_notes']
        lines.append(f'| {q["id"]} | {len(n["added_chunks"])} | {len(n["removed_chunk_ids"])} | {len(q["evidence_groups"])} | {q["scoring_disposition"]} |')
    for q in records:
        lines += ['', f'## {q["id"]}', '', q['question'], '', '**候选答案：** ' + q['expected_answer'], '',
                  '**Rubric：** ' + '；'.join(q['rubric'])]
        for g in q['evidence_groups']:
            lines += ['', f'- {g["id"]}：{g["fact"]}；状态 {g["status"]}',
                      '  - 支持 Chunk：' + (', '.join(g['supporting_chunk_ids']) or '无；明确暂缓，不伪造证据')]
        for item in q['review_notes']['added_chunks']:
            lines += ['', f'- 新增 `{item["chunk_id"]}`（{item["source_path"]} #{item["chunk_index"]}）',
                      '  - 支持：' + '；'.join(f'{g["fact_id"]} {g["fact"]}' for g in item['supports'])]
        if q['review_notes']['removed_chunk_ids']:
            lines += ['', '- 移除关联：' + ', '.join(q['review_notes']['removed_chunk_ids'])]
    lines += ['', '## 校验', '',
              '结果：' + validation['status'],
              '无效 Chunk、重复证据条目、位置错配、孤立组与非预期缺组均应为零。',
              '同一事实在多个真实位置重复出现，属于替代证据；同一证据支持多组不属于重复条目。',
              '结构通过不代表标注已获人工确认；没有自动将任何记录标记为 human_reviewed=true。']
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'validate'])
    args = parser.parse_args()
    if args.action == 'build':
        for path in (PROPOSAL, SUMMARY, VALIDATION):
            if path.exists():
                raise SystemExit(f'Refusing to overwrite existing proposal artifact: {path.name}')
        protected = protected_hashes()
        records = make_records()
        report = validate(records, protected)
        if not report['structural_validation_passed']:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            raise SystemExit(1)
        PROPOSAL.write_text(''.join(json.dumps(q, ensure_ascii=False) + '\n' for q in records), encoding='utf-8')
        SUMMARY.write_text(summary(records, report), encoding='utf-8')
        report['proposal_sha256'] = sha(PROPOSAL)
        report['summary_sha256'] = sha(SUMMARY)
        report['generator_sha256'] = sha(Path(__file__))
        VALIDATION.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    else:
        baseline = load(VALIDATION)
        records = [json.loads(line) for line in PROPOSAL.read_text(encoding='utf-8').splitlines()]
        report = validate(records, baseline['protected_input_hashes'])
        if sha(PROPOSAL) != baseline['proposal_sha256'] or sha(SUMMARY) != baseline['summary_sha256'] or sha(Path(__file__)) != baseline['generator_sha256']:
            report['structural_validation_passed'] = False
            report['status'] = 'failed'
            report['errors'].append('Proposal, summary or generator hash changed')
        if not report['structural_validation_passed']:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            raise SystemExit(1)
    print(json.dumps({k: v for k, v in report.items() if k != 'protected_input_hashes'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
