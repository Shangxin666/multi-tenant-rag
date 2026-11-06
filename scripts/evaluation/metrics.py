"""Binary chunk relevance, macro query averages; duplicate ranks consume slots."""
import math
import statistics

KS = (1, 3, 5, 10)


def retrieval_metrics(ranked: list[str], relevant: list[str]) -> dict:
    truth = set(relevant)
    if not truth:
        return {}
    result = {}
    for k in KS:
        hits = len(set(ranked[:k]) & truth)
        result[f'recall@{k}'] = hits / len(truth)
        result[f'hit_rate@{k}'] = float(hits > 0)
    result['mrr@10'] = next((1 / i for i, key in enumerate(ranked[:10], 1) if key in truth), 0.)
    seen = set()
    dcg = 0.
    for i, key in enumerate(ranked[:10], 1):
        if key in truth and key not in seen:
            dcg += 1 / math.log2(i + 1)
        seen.add(key)
    result['ndcg@10'] = dcg / sum(1 / math.log2(i + 1) for i in range(1, min(10, len(truth)) + 1))
    return result


def aggregate(rows: list[dict]) -> dict:
    scored = [r['metrics'] for r in rows if r['answerable']]
    negative = [r for r in rows if not r['answerable']]
    times = sorted(r['latency_ms'] for r in rows)
    def percentile(p):
        if not times:
            return None
        pos = (len(times) - 1) * p
        lo = int(pos)
        return times[lo] + (times[min(lo + 1, len(times) - 1)] - times[lo]) * (pos - lo)
    return {'n': len(rows), 'answerable_n': len(scored), 'unanswerable_n': len(negative),
            'metrics': {k: statistics.mean(s[k] for s in scored) for k in scored[0]} if scored else {},
            'no_result_accuracy': statistics.mean(not r['ranked'] for r in negative) if negative else None,
            'answerable_false_empty_rate': statistics.mean(not r['ranked'] for r in rows if r['answerable']) if scored else None,
            'scope_violation_count': sum(len(r['scope_violations']) for r in rows),
            'p50_ms': percentile(.5), 'p95_ms': percentile(.95)}
