"""Build/validate this candidate snapshot with production parsing; never run models."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import sys
from uuid import UUID, uuid5

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[3]
sys.path.insert(0, str(REPO / 'src'))
from app.modules.documents.ingestion.parsers import parse_document
from app.modules.documents.ingestion.chunking import split_sections

NS = UUID('751d658d-1e97-46b1-a5ba-ad655e945d70')
SIZE, OVERLAP = 1000, 150
LICENSE_ID = 'CC-BY-NC-SA-4.0'
LICENSE_BASIS = 'Chinese translation README.md:51; root LICENSE instead states CC BY 4.0; both original notices retained'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def stable(key):
    return str(uuid5(NS, key))


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows), encoding='utf-8')


def history_hashes():
    roots = [REPO / 'tests/fixtures/evaluation/v2', REPO / 'docs/evaluation/v2']
    return {p.relative_to(REPO).as_posix(): digest(p.read_bytes())
            for root in roots for p in sorted(root.rglob('*')) if p.is_file()}


def headings(text):
    result, stack = [], []
    fence = None
    offset = 0
    for number, line in enumerate(text.splitlines(keepends=True), 1):
        stripped = line.lstrip()
        marker = re.match(r'(`{3,}|~{3,})', stripped)
        if marker:
            char = marker[1][0]
            if fence is None:
                fence = (char, len(marker[1]))
            elif char == fence[0] and len(marker[1]) >= fence[1]:
                fence = None
        elif fence is None:
            match = re.match(r'^(#{1,6})\s+(.+?)\s*$', line)
            if match:
                level, title = len(match[1]), match[2]
                anchor = re.search(r'\{#([^}]+)\}', title)
                title = re.sub(r'\s*\{#[^}]+\}', '', title)
                stack = [h for h in stack if h['level'] < level]
                item = {'level': level, 'title': title, 'anchor': anchor[1] if anchor else None,
                        'line': number, 'char_start': offset}
                stack.append(item)
                result.append({**item, 'section_path': [h['title'] for h in stack]})
        offset += len(line)
    return result


def line_number(text, offset):
    return text.count('\n', 0, offset) + 1


def section_at(sections, line):
    preceding = [s for s in sections if s['line'] <= line]
    return preceding[-1] if preceding else None


def build():
    if (ROOT / 'dataset.json').exists():
        raise SystemExit('Refusing to overwrite an existing annotated snapshot')
    previous = history_hashes()
    upstream = read(ROOT / 'upstream.json')
    license_text = (ROOT / 'licenses/upstream-LICENSE.txt').read_text(encoding='utf-8')
    translation_notice = (ROOT / 'licenses/upstream-README.md').read_text(encoding='utf-8')
    if 'licensed under [CC BY 4.0]' not in license_text:
        raise ValueError('Upstream license changed; inspect before preparing')
    if 'by-nc-sa/4.0/' not in translation_notice:
        raise ValueError('Chinese translation license notice changed; inspect before preparing')
    revision = upstream['commit']
    tenant = stable('tenant:vue3-zh-public-evaluation')
    kb = stable('knowledge-base:vue3-zh:real-tech-v1:candidate')
    documents, chunks, parsed, sources = [], [], [], []
    texts, sections_by_doc = {}, {}
    for source in upstream['files']:
        if not source['source_path'].startswith('src/'):
            continue
        path = ROOT / source['local_path']
        assert digest(path.read_bytes()) == source['sha256']
        sections = parse_document(path, 'markdown', 200, 2_000_000)
        assert len(sections) == 1
        text = sections[0].text
        assert text == path.read_text(encoding='utf-8-sig')
        marks = headings(text)
        did = stable(f'document:{revision}:{source["source_path"]}:{source["sha256"]}')
        texts[did], sections_by_doc[did] = text, marks
        title = marks[0]['title']
        source_record = {**source, 'document_id': did, 'repository': upstream['repository'],
                         'commit': revision, 'product': 'Vue', 'product_major_version': 3,
                         'product_version_note': 'Vue 3 docs snapshot; per-API 3.4/3.5 boundaries retained in source, not a version tag',
                         'language': 'zh-CN', 'license_id': LICENSE_ID,
                         'license_url': 'https://creativecommons.org/licenses/by-nc-sa/4.0/',
                         'license_basis': LICENSE_BASIS, 'repository_LICENSE_id': 'CC-BY-4.0',
                         'attribution': 'Vue 官方中文文档翻译维护者及贡献者；Yuxi (Evan) You and Vue documentation contributors',
                         'copyright': license_text.splitlines()[0], 'modifications': 'none; source bytes retained',
                         'images_downloaded': False, 'retrieved_at': upstream['retrieved_at']}
        sources.append(source_record)
        doc = {'id': did, 'title': title, 'tenant_id': tenant, 'knowledge_base_id': kb,
               'path': source['local_path'], 'source_path': source['source_path'],
               'source_url': source['source_url'], 'source_type': 'markdown', 'synthetic': False,
               'sha256': source['sha256'], 'split': 'unassigned', 'language': 'zh-CN',
               'document_family_id': 'vue3:reactivity' if 'reactivity' in source['source_path'] or any(x in source['source_path'] for x in ('computed','watchers','composables')) else 'vue3:component-contracts',
               'license_id': LICENSE_ID, 'license_basis': LICENSE_BASIS, 'commit': revision}
        documents.append(doc)
        parsed.append({'document_id': did, 'sections': [{'text': s.text, 'metadata': s.metadata} for s in sections],
                       'headings': marks, 'offset_coordinate': 'Unicode characters in parser output; LF newlines'})
        previous_start = -1
        drafts = split_sections(sections, SIZE, OVERLAP, 5000)
        for draft in drafts:
            start = text.find(draft.content, previous_start + 1)
            if start < 0:
                raise ValueError('Cannot map chunk to unchanged parser output')
            end = start + len(draft.content)
            previous_start = start
            cid = stable(f'chunk:{did}:{SIZE}:{OVERLAP}:{draft.chunk_index}:{digest(draft.content.encode())}')
            first_line, last_line = line_number(text, start), line_number(text, end - 1)
            chunks.append({'id': cid, 'document_id': did, 'tenant_id': tenant, 'knowledge_base_id': kb,
                           'chunk_index': draft.chunk_index, 'content': draft.content,
                           'metadata': draft.metadata, 'source_path': source['source_path'],
                           'char_start': start, 'char_end': end, 'line_start': first_line, 'line_end': last_line,
                           'section_at_start': section_at(marks, first_line),
                           'section_headings_inside': [h for h in marks if first_line <= h['line'] <= last_line]})
        doc['chunk_count'] = len(drafts)
    by_source = {d['source_path'][4:]: d for d in documents}
    cases = []
    for spec in read(ROOT / 'candidate_specs.json'):
        evidence = []
        for index, (source_path, first, last) in enumerate(spec['evidence'], 1):
            doc = by_source[source_path]
            text = texts[doc['id']]
            lines = text.splitlines(keepends=True)
            quote = ''.join(lines[first - 1:last]).rstrip('\n')
            if not quote.strip():
                raise ValueError('Empty evidence')
            start = sum(len(line) for line in lines[:first - 1])
            end = start + len(quote)
            matches = [c for c in chunks if c['document_id'] == doc['id'] and quote in c['content']]
            if not matches:
                raise ValueError(f'{spec["id"]} evidence crosses chunk boundary; choose an atomic excerpt')
            mark = section_at(sections_by_doc[doc['id']], first)
            evidence.append({'id': f'{spec["id"]}-E{index}', 'document_id': doc['id'], 'quote': quote,
                             'role': 'supporting_candidate', 'location': {
                                 'source_path': doc['source_path'], 'line_start': first, 'line_end': last,
                                 'char_start': start, 'char_end': end, 'section': mark,
                                 'source_url': doc['source_url'] + f'#L{first}-L{last}'},
                             'chunk_ids': [c['id'] for c in matches],
                             'mapping_method': 'document-level source excerpt -> all containing chunks in that document'})
        candidate_ids = sorted({cid for e in evidence for cid in e['chunk_ids']})
        negative = not bool(evidence)
        # Same-claim corroboration: these are alternatives, not additional required facts.
        if spec['id'] == 'VUE029':
            groups = [{'id': 'G1', 'role': 'necessary', 'alternative_evidence_ids': [e['id'] for e in evidence]}]
        elif spec['id'] == 'VUE030':
            groups = [{'id': 'G1', 'role': 'necessary', 'alternative_evidence_ids': [evidence[0]['id'], evidence[2]['id']]},
                      {'id': 'G2', 'role': 'necessary', 'alternative_evidence_ids': [evidence[1]['id']]}]
        else:
            groups = [{'id': f'G{i}', 'role': 'necessary', 'alternative_evidence_ids': [e['id']]}
                      for i, e in enumerate(evidence, 1)]
        cases.append({'id': spec['id'], 'question': spec['question'], 'expected_answer': spec['expected_answer'],
                      'answer_rubric': spec['rubric'], 'answerable': not negative, 'category': spec['category'],
                      'requested_version': spec.get('requested_version', 'Vue 3; respect source version badges'),
                      'question_language': 'zh-CN', 'tenant_id': tenant, 'knowledge_base_id': kb, 'split': 'unassigned',
                      'source_document_ids': sorted({e['document_id'] for e in evidence}),
                      'relevant_document_ids': sorted({e['document_id'] for e in evidence}),
                      'evidence_quotes': [e['quote'] for e in evidence],
                      'evidence_locations': [e['location'] for e in evidence], 'evidence': evidence,
                      'evidence_groups': groups, 'distractor_evidence': [],
                      'relevant_chunk_ids': candidate_ids,
                      'human_reviewed': False, 'review_status': 'unverified', 'eligible_for_trusted_evaluation': False,
                      'generation_method': 'AI-assisted candidate drafting grounded in selected source excerpts; no human adjudication',
                      'reviewer': None, 'reviewed_at': None,
                      'annotation_notes': '机器仅核验原文位置及字面包含；答案、必要/替代证据组、语义相关性与遗漏均待人工审核。负样本暂无支持证据，不伪造 Chunk ID。',
                      'relevance_complete': False, 'negative_reason': spec.get('negative_reason'),
                      'negative_review': {'scope_document_ids': [d['id'] for d in documents],
                                          'search_terms': spec.get('negative_search_terms', []),
                                          'literal_search_hits': {term: [d['id'] for d in documents if term.casefold() in texts[d['id']].casefold()]
                                                                  for term in spec.get('negative_search_terms', [])},
                                          'absence_verified_by_human': False} if negative else None})
    data = {'version': 'real-tech-v1-vue3-zh-candidate-0.1', 'status': 'candidate-unverified',
            'license_id': LICENSE_ID, 'license_basis': LICENSE_BASIS,
            'trusted_evaluation_allowed': False, 'source_repository': upstream['repository'], 'source_commit': revision,
            'chunk_size': SIZE, 'chunk_overlap': OVERLAP, 'chunk_length_unit': 'Unicode characters via len',
            'split_policy': 'unassigned; review document-family/evidence dependencies before Dev/Final freeze',
            'documents': documents, 'chunks': chunks, 'cases': cases}
    write(ROOT / 'sources.json', {'repository': upstream['repository'], 'commit': revision, 'documents': sources})
    jsonl(ROOT / 'parsed.jsonl', parsed)
    jsonl(ROOT / 'chunks.jsonl', chunks)
    jsonl(ROOT / 'annotations/candidates.jsonl', cases)
    write(ROOT / 'dataset.json', data)
    counts = {'documents': len(documents), 'chunks': len(chunks), 'average_chunks_per_document': len(chunks) / len(documents),
              'cases': len(cases), 'answerable_candidates': sum(q['answerable'] for q in cases),
              'categories': dict(Counter(q['category'] for q in cases)),
              'unique_candidate_evidence_chunks': len({c for q in cases for c in q['relevant_chunk_ids']}),
              'verified_cases': 0, 'trusted_evaluation_cases': 0, 'experiment_records': 0,
              'per_document': [{k: d[k] for k in ('id', 'title', 'source_path', 'chunk_count')} for d in documents],
              'query_scopes': [{'tenant_id': tenant, 'knowledge_base_id': kb, 'documents': len(documents),
                                'candidate_chunks': len(chunks), 'queries': len(cases)}]}
    write(ROOT / 'statistics.json', counts)
    lines = ['# Vue 3 中文真实语料候选集审核', '', '**全部 30 题均为 unverified，不得进入可信最终评测。**', '',
             f'固定 Commit：`{revision}`。', f'15 份原始 Markdown，{len(chunks)} 个 Chunk；单个查询知识库包含全部 {len(chunks)} 个候选 Chunk。', '',
             '| 源文件 | Chunk 数 |', '| --- | ---: |']
    lines += [f'| {d["source_path"]} | {d["chunk_count"]} |' for d in documents]
    for q in cases:
        lines += ['', f'## {q["id"]} · {q["category"]} · unverified', '', q['question'], '',
                  '**候选标准答案：** ' + q['expected_answer'], '', '**评价点：** ' + '；'.join(q['answer_rubric']), '']
        if not q['evidence']:
            lines += ['无答案候选：无支持证据、无相关 Chunk。缺失性判断仍待人工复核。']
        for e in q['evidence']:
            loc = e['location']
            lines += [f'- 来源：[{loc["source_path"]}:{loc["line_start"]}]({loc["source_url"]})',
                      '- 章节：' + ' / '.join(loc['section']['section_path']),
                      '- Chunk：' + ', '.join(e['chunk_ids']), '', '```text', e['quote'], '```', '']
    (ROOT / 'REVIEW.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (ROOT / 'dataset.sha256').write_text(digest((ROOT / 'dataset.json').read_bytes()) + '\n', encoding='ascii')
    pipeline = ['src/app/modules/documents/ingestion/parsers.py', 'src/app/modules/documents/ingestion/chunking.py',
                'src/app/modules/documents/ingestion/types.py']
    manifest = {'dataset_version': data['version'], 'prepared_at': datetime.now(timezone.utc).isoformat(),
                'source_commit': revision, 'source_license': LICENSE_ID,
                'license_discrepancy': LICENSE_BASIS,
                'parser_files': {p: digest((REPO / p).read_bytes()) for p in pipeline},
                'packages': {name: importlib.metadata.version(name) for name in ('langchain-text-splitters', 'pypdf', 'beautifulsoup4')},
                'python': sys.version, 'chunk_config': {'size': SIZE, 'overlap': OVERLAP, 'max_chunks_per_document': 5000},
                'historical_v2_hashes': previous,
                'files': {p.relative_to(ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(ROOT.rglob('*'))
                          if p.is_file() and p.name not in ('manifest.json', 'validation.json') and '__pycache__' not in p.parts}}
    write(ROOT / 'manifest.json', manifest)
    return validate()


def validate():
    manifest = read(ROOT / 'manifest.json')
    data = read(ROOT / 'dataset.json')
    assert digest((ROOT / 'dataset.json').read_bytes()) == (ROOT / 'dataset.sha256').read_text().strip()
    for name, expected in manifest['files'].items():
        assert digest((ROOT / name).read_bytes()) == expected, name
    for name, expected in manifest['parser_files'].items():
        assert digest((REPO / name).read_bytes()) == expected, name
    for name, expected in manifest['historical_v2_hashes'].items():
        assert digest((REPO / name).read_bytes()) == expected, name
    docs = {d['id']: d for d in data['documents']}
    chunks = {c['id']: c for c in data['chunks']}
    assert len(docs) == 15 and len(chunks) == len(data['chunks'])
    assert len(data['cases']) == 30 and len({q['id'] for q in data['cases']}) == 30
    assert len({q['question'] for q in data['cases']}) == 30
    assert len({c['content'] for c in chunks.values()}) == len(chunks)
    reconstructed = 0
    for d in docs.values():
        path = ROOT / d['path']
        assert digest(path.read_bytes()) == d['sha256']
        sections = parse_document(path, 'markdown', 200, 2_000_000)
        drafts = split_sections(sections, SIZE, OVERLAP, 5000)
        stored = sorted([c for c in chunks.values() if c['document_id'] == d['id']], key=lambda c: c['chunk_index'])
        assert len(drafts) == len(stored) == d['chunk_count']
        for draft, c in zip(drafts, stored, strict=True):
            assert draft.content == c['content'] and draft.metadata == c['metadata']
            assert sections[0].text[c['char_start']:c['char_end']] == c['content']
            assert len(c['content']) <= SIZE
            reconstructed += 1
    for q in data['cases']:
        assert q['review_status'] == 'unverified' and not q['human_reviewed'] and not q['eligible_for_trusted_evaluation']
        assert q['answerable'] == bool(q['evidence'])
        assert set(q['relevant_chunk_ids']) == {cid for e in q['evidence'] for cid in e['chunk_ids']}
        for e in q['evidence']:
            d = docs[e['document_id']]
            text = parse_document(ROOT / d['path'], 'markdown', 200, 2_000_000)[0].text
            loc = e['location']
            assert text[loc['char_start']:loc['char_end']] == e['quote']
            assert e['quote'] == '\n'.join(text.splitlines()[loc['line_start'] - 1:loc['line_end']]).rstrip('\n')
            for cid in e['chunk_ids']:
                c = chunks[cid]
                assert e['quote'] in c['content']
                assert c['document_id'] == d['id']
                assert all(c[k] == q[k] for k in ('tenant_id', 'knowledge_base_id'))
        if q['category'] == 'multi_evidence':
            assert len(q['source_document_ids']) >= 2
    result = {'status': 'passed', 'scope': 'structural checks only; not human semantic validation',
              'documents': len(docs), 'rebuilt_chunks': reconstructed, 'cases': 30,
              'all_unverified': True, 'trusted_evaluation_cases': 0,
              'historical_v2_files_unchanged': len(manifest['historical_v2_hashes']),
              'models_loaded': False, 'database_accessed': False}
    write(ROOT / 'validation.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'validate'])
    args = parser.parse_args()
    print(json.dumps(build() if args.action == 'build' else validate(), ensure_ascii=False, indent=2))
