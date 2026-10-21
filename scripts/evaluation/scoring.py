"""Rule proxies are deliberately separate from reviewed semantic judgments."""
import hashlib
import json
import re
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def retrieval(ranked: list[str], relevant: list[str], k: int = 5) -> dict:
    ranked = list(dict.fromkeys(ranked))
    truth = set(relevant)
    if not truth:
        return {'recall': None, 'mrr': None}
    return {'recall': len(set(ranked[:k]) & truth)/len(truth),
            'mrr': next((1/i for i, key in enumerate(ranked[:k], 1) if key in truth), 0.0)}


def rule_score(case: dict, answer: str, evidence: dict[str, str], calls: list[dict]) -> dict:
    # This is an explicit closed-fact lexical proxy, not unrestricted semantic grading.
    checks = [any(alias.casefold() in answer.casefold() for alias in fact) for fact in case['facts']]
    refused = any(word in answer for word in ('不足', '没有', '未提供', '无法', '未找到', '未检索', '不能'))
    refs = set(re.findall(r'\[?(S\d+)\]?', answer))
    known = refs <= evidence.keys()
    selected = {c['name'] for c in calls}
    allowed = set(case.get('allowed_tools', []))
    required = set(case.get('required_tools', []))
    tools_ok = selected <= allowed and required <= selected if case['mode'] == 'agent' else None
    forbidden = any(v.casefold() in answer.casefold() for v in case.get('forbidden', []))
    correct = refused if case['no_answer'] else bool(checks) and all(checks) and not forbidden
    argument_valid = sum(c['valid'] for c in calls)
    return {'fact_alias_coverage': sum(checks)/len(checks) if checks else None,
            'answer_rule_pass': correct, 'refusal_rule': refused,
            'citation_ids_valid': known, 'citation_present': bool(refs),
            'tool_selection_pass': tools_ok,
            'argument_valid_count': argument_valid, 'argument_attempts': len(calls),
            'argument_valid_rate': argument_valid/len(calls) if calls else None,
            'task_rule_pass': bool(correct and known and (case['no_answer'] or bool(refs))
                                   and tools_ok is not False and argument_valid == len(calls))}


def reviewed_score(record: dict, review: dict | None) -> dict:
    if review is None:
        return {'review_status': 'unreviewed', 'answer_correctness': None, 'faithfulness': None,
                'citation_support': None, 'task_completed': None}
    if review['record_hash'] != digest(record):
        raise ValueError('Review does not match immutable run record')
    if review['reviewer_type'] not in ('human', 'model_assisted') or not review.get('reviewer'):
        raise ValueError('Reviewer provenance required')
    if review['correctness'] not in (0, 0.5, 1):
        raise ValueError('Invalid correctness score')
    if type(review['task_completed']) is not bool or not review.get('rationale'):
        raise ValueError('Completion and rationale required')
    supported = 0
    cited, cited_supported = 0, 0
    for claim in review['claims']:
        if not claim['text'] or claim['text'] not in record['answer']:
            raise ValueError('Claim must be an exact answer excerpt')
        if claim['verdict'] not in ('supported', 'contradicted', 'unsupported', 'uncertain'):
            raise ValueError('Invalid claim verdict')
        is_cited = bool(claim.get('source_id') and f"[{claim['source_id']}]" in record['answer'])
        if is_cited:
            cited += 1
        if claim['verdict'] == 'supported':
            evidence = record['evidence'].get(claim.get('source_id'), '')
            if not claim.get('quote') or claim['quote'] not in evidence:
                raise ValueError('Support must quote actual model-visible evidence')
            supported += 1
            cited_supported += int(is_cited)
    return {'review_status': review['reviewer_type'], 'answer_correctness': review['correctness'],
            'faithfulness': supported/len(review['claims']) if review['claims'] else None,
            'citation_support': cited_supported/cited if cited else None,
            'task_completed': review['task_completed']}


def summarize(records: list[dict], reviews: dict | None = None) -> dict:
    reviews = reviews or {}
    output = {}
    for split in ('dev', 'holdout'):
        for mode in ('rag', 'agent'):
            rows = [r for r in records if r['split'] == split and r['mode'] == mode]
            if not rows:
                continue
            judged = [reviewed_score(r, reviews.get(r['case_id'])) for r in rows]
            errors = {}
            for row in rows:
                if row['error']:
                    errors[row['error']] = errors.get(row['error'], 0)+1
            output[f'{split}/{mode}'] = {'n': len(rows), 'errors': errors,
                'rule_task_pass_rate': sum(r['rules']['task_rule_pass'] and not r['error'] for r in rows)/len(rows),
                'human_reviewed': sum(j['review_status'] == 'human' for j in judged),
                'model_assisted_reviewed': sum(j['review_status'] == 'model_assisted' for j in judged),
                'unreviewed': sum(j['review_status'] == 'unreviewed' for j in judged)}
            for reviewer in ('human', 'model_assisted'):
                for metric in ('answer_correctness', 'faithfulness', 'citation_support', 'task_completed'):
                    vals = [j[metric] for j in judged if j['review_status'] == reviewer and j[metric] is not None]
                    output[f'{split}/{mode}'][f'{reviewer}/{metric}'] = {'n': len(vals), 'mean': sum(vals)/len(vals) if vals else None}
    return output
