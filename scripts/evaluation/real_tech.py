"""Small adapter/report supplement for explicitly unverified offline development runs."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics

from scripts.evaluation.metrics import KS, aggregate


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_exploratory(root: Path, *, allow_unverified: bool):
    if not allow_unverified:
        raise ValueError('Explicit --allow-unverified-exploratory is required')
    data = json.loads((root / 'dataset.json').read_text(encoding='utf-8'))
    if file_sha(root / 'dataset.json') != (root / 'dataset.sha256').read_text().strip():
        raise ValueError('Frozen corpus hash mismatch')
    if (data['chunk_size'], data['chunk_overlap']) != (1000, 150):
        raise ValueError('Expected frozen 1000/150 chunk configuration')
    annotation_path = root / 'annotations/content-review-draft.jsonl'
    audit = json.loads((root / 'content-review-draft-validation.json').read_text(encoding='utf-8'))
    output_hashes = {name.replace('\\', '/'): value for name, value in audit['output_sha256'].items()}
    if file_sha(annotation_path) != output_hashes['annotations/content-review-draft.jsonl']:
        raise ValueError('Content-review snapshot hash mismatch')
    protected = {str((root / name).resolve()): file_sha(root / name)
                 for name in json.loads((root / 'manifest.json').read_text(encoding='utf-8'))['files']}
    for name in ('manifest.json', 'annotations/review-proposal.jsonl', 'annotations/content-review-draft.jsonl',
                 'content-review-draft-validation.json'):
        protected[str((root / name).resolve())] = file_sha(root / name)
    repo = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    for name, expected in manifest['historical_v2_hashes'].items():
        path = repo / name
        if file_sha(path) != expected:
            raise ValueError('Historical v2 file drift: ' + name)
        protected[str(path.resolve())] = expected
    metric_path = Path(__file__).with_name('metrics.py')
    protected[str(metric_path.resolve())] = file_sha(metric_path)
    for name, expected in manifest['files'].items():
        if file_sha(root / name) != expected:
            raise ValueError('Frozen source artifact drift: ' + name)
    cases = [json.loads(line) for line in annotation_path.read_text(encoding='utf-8').splitlines()]
    chunks = {c['id']: c for c in data['chunks']}
    documents = {d['id']: d for d in data['documents']}
    if len(chunks) != 215 or len(documents) != 15 or len(cases) != 30:
        raise ValueError('Unexpected corpus/candidate size')
    if {q['id'] for q in cases} != {f'VUE{i:03d}' for i in range(1, 31)}:
        raise ValueError('Unexpected case IDs')
    for d in documents.values():
        if file_sha(root / d['path']) != d['sha256']:
            raise ValueError('Source Markdown hash mismatch')
    selected = []
    for original in cases:
        if original['id'] == 'VUE026':
            if original['eligible_after_human_review']:
                raise ValueError('VUE026 must remain deferred')
            continue
        if not original['assistant_content_review_passed']:
            raise ValueError('Selected case has not passed assisted content review')
        if original['review_status'] != 'unverified' or original['human_reviewed'] is not False:
            raise ValueError('Unexpected review state; do not silently reclassify a different snapshot')
        if original['relevance_exhaustiveness_verified'] or original['eligible_for_trusted_evaluation']:
            raise ValueError('Expected explicitly non-gold exploratory snapshot')
        relevant = set(original['relevant_chunk_ids'])
        for cid in relevant:
            if cid not in chunks or any(chunks[cid][k] != original[k] for k in ('tenant_id', 'knowledge_base_id')):
                raise ValueError('Invalid or unauthorized relevance label')
        if original['answerable']:
            groups = original['evidence_groups']
            if not relevant or not groups or any(not g['supporting_chunk_ids'] for g in groups):
                raise ValueError('Answerable case missing evidence group')
            if {c for g in groups for c in g['supporting_chunk_ids']} != relevant:
                raise ValueError('Group/relevance union mismatch')
        elif relevant or original['evidence_groups']:
            raise ValueError('Negative case must have no positive evidence')
        q = deepcopy(original)
        q['original_split'] = q['split']
        q['split'] = 'dev'  # In-memory experiment partition only; source status is untouched.
        selected.append(q)
    counts = {'documents': len(documents), 'chunks': len(chunks), 'candidate_cases': len(cases),
              'cases': len(selected), 'answerable': sum(q['answerable'] for q in selected),
              'negative': sum(not q['answerable'] for q in selected), 'excluded_cases': ['VUE026'],
              'categories': dict(Counter(q['category'] for q in selected))}
    data = {**data, 'cases': selected}
    metadata = {'experiment_class': 'exploratory', 'annotation_status': 'unverified',
                'human_gold': False, 'independent_final': False, 'relevance_exhaustiveness_verified': False,
                'annotation_file': str(annotation_path), 'annotation_sha256': file_sha(annotation_path),
                'excluded_cases': ['VUE026'], 'protected_input_sha256': protected,
                'evidence_group_formula': '|necessary groups with >=1 directly supporting Chunk in top K| / |necessary groups|; macro over answerable queries only',
                'database_used': False, 'parameters_tuned': False}
    return data, counts, metadata


def evidence_group_metrics(ranked, groups):
    required = [g for g in groups if g['role'] == 'necessary']
    if not required:
        return {}
    if any(not g['supporting_chunk_ids'] for g in required):
        raise ValueError('Do not score a case with an unresolved necessary group')
    return {f'evidence_group_coverage@{k}': sum(bool(set(ranked[:k]) & set(g['supporting_chunk_ids']))
                                              for g in required) / len(required) for k in KS}


def enrich_record(row, case, timings):
    scored = [cid if cid not in row['scope_violations'] else 'SCOPE_VIOLATION' for cid in row['ranked']]
    groups = [g for g in case['evidence_groups'] if g['role'] == 'necessary']
    row.update(experiment_class='exploratory', annotation_status=case['review_status'],
               human_reviewed=case['human_reviewed'], relevance_exhaustiveness_verified=False,
               assistant_content_review_passed=case['assistant_content_review_passed'],
               original_split=case['original_split'], timings_ms=timings,
               evidence_groups=groups,
               evidence_group_metrics=evidence_group_metrics(scored, groups) if case['answerable'] else {},
               missing_relevant_chunk_ids=sorted(set(case['relevant_chunk_ids']) - set(scored)),
               uncovered_group_ids=[g['id'] for g in groups if not set(scored) & set(g['supporting_chunk_ids'])])
    row['failure_reasons'] = []
    if row['missing_relevant_chunk_ids']:
        row['failure_reasons'].append('labeled_relevant_chunks_missing_at_10')
    if row['uncovered_group_ids']:
        row['failure_reasons'].append('necessary_evidence_groups_uncovered_at_10')
    if not case['answerable'] and row['ranked']:
        row['failure_reasons'].append('negative_query_returned_results')
    if row['scope_violations']:
        row['failure_reasons'].append('scope_violation')
    row['failed'] = bool(row['failure_reasons'])


def compare_pair(dense, reranked):
    if not dense['answerable']:
        return
    checks = ('recall@10', 'mrr@10', 'ndcg@10')
    worsened = [key for key in checks if reranked['metrics'][key] < dense['metrics'][key]]
    if reranked['evidence_group_metrics']['evidence_group_coverage@10'] < dense['evidence_group_metrics']['evidence_group_coverage@10']:
        worsened.append('evidence_group_coverage@10')
    reranked['worsened_vs_dense'] = worsened
    if worsened:
        reranked['failure_reasons'].append('rerank_worsened_vs_dense')
        reranked['failed'] = True


def summarize_exploratory(report):
    for strategy, summary in report['summary'].items():
        rows = [r for r in report['records'] if r['strategy'] == strategy]
        positive = [r for r in rows if r['answerable']]
        summary['evidence_group_metrics'] = {
            f'evidence_group_coverage@{k}': statistics.mean(r['evidence_group_metrics'][f'evidence_group_coverage@{k}'] for r in positive)
            for k in KS} if positive else {}
        summary['stage_timings_ms'] = {}
        for stage in ('query_embedding', 'dense_search', 'cross_encoder_rerank'):
            # Reuse the exact existing percentile implementation via aggregate.
            temporary = [{**r, 'latency_ms': r['timings_ms'][stage]} for r in rows]
            quantiles = aggregate(temporary)
            summary['stage_timings_ms'][stage] = {'p50_ms': quantiles['p50_ms'], 'p95_ms': quantiles['p95_ms']}
    report['failure_cases'] = [{'case_id': r['case_id'], 'strategy': r['strategy'],
                               'reasons': r['failure_reasons'],
                               'missing_relevant_chunk_ids': r['missing_relevant_chunk_ids'],
                               'uncovered_group_ids': r['uncovered_group_ids'],
                               'worsened_vs_dense': r.get('worsened_vs_dense', [])}
                              for r in report['records'] if r['failed']]


def render_exploratory(report):
    lines = ['\n## Exploratory / unverified — not independent Final or human gold', '',
             '开发探索；VUE026 排除；未改任何人工审核状态。相关 Chunk 标注尚未穷尽，指标仅相对于当前候选标签。',
             '无答案样本不进入 Recall/MRR/nDCG/证据组覆盖率分母。空结果率不是最终回答拒答正确率。',
             '离线 NumPy 精确余弦，不使用 PostgreSQL；无 LLM。单次顺序 CPU 实验，无调参、无 HTTP/并发基准。', '',
             '| Strategy | EGC@1 | EGC@3 | EGC@5 | EGC@10 |', '| --- | ---: | ---: | ---: | ---: |']
    for name, value in report.get('summary', {}).items():
        groups = value['evidence_group_metrics']
        lines.append('| ' + name + ' | ' + ' | '.join(f'{groups[f"evidence_group_coverage@{k}"]:.4f}' for k in KS) + ' |')
    lines += ['', '## Stage timing (milliseconds)', '',
              'Query 编码和 Dense 结果在两策略间共享测量；Rerank 总耗时累加这两段和实际重排耗时。冷加载/语料编码及报告写入不计入逐题时间。', '',
              '| Strategy | Stage | P50 | P95 |', '| --- | --- | ---: | ---: |']
    for name, value in report.get('summary', {}).items():
        for stage, latency in value['stage_timings_ms'].items():
            lines.append(f'| {name} | {stage} | {latency["p50_ms"]:.3f} | {latency["p95_ms"]:.3f} |')
    lines += ['', '## Per-query ranks and metrics', '']
    for row in report['records']:
        lines += [f'### {row["case_id"]} / {row["strategy"]}', '', row['question'], '',
                  'Metrics: ' + json.dumps(row['metrics'], ensure_ascii=False),
                  'Evidence groups: ' + json.dumps(row['evidence_group_metrics']),
                  'Stage ms: ' + json.dumps(row['timings_ms']),
                  'Top10: ' + ', '.join(f'{i}:{cid}' for i, cid in enumerate(row['ranked'], 1)),
                  'Failures: ' + (', '.join(row['failure_reasons']) or 'none'), '']
    return '\n'.join(lines)
