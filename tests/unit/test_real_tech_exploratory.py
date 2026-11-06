from pathlib import Path

import pytest

from scripts.evaluation.real_tech import evidence_group_metrics, load_exploratory
from scripts.evaluation.metrics import retrieval_metrics


def test_group_alternatives_and_one_chunk_covering_multiple_facts():
    groups = [dict(role='necessary', supporting_chunk_ids=['a', 'b']),
              dict(role='necessary', supporting_chunk_ids=['b', 'c'])]
    assert evidence_group_metrics(['b'], groups)['evidence_group_coverage@1'] == 1
    assert evidence_group_metrics(['a', 'a'], groups)['evidence_group_coverage@3'] == .5
    assert retrieval_metrics(['a'], ['a', 'b', 'c'])['recall@1'] == 1 / 3
    assert evidence_group_metrics([], []) == {}
    with pytest.raises(ValueError):
        evidence_group_metrics([], [dict(role='necessary', supporting_chunk_ids=[])])


def test_exploratory_requires_explicit_opt_in_and_preserves_review_flags():
    root = Path(__file__).resolve().parents[2] / 'tests/fixtures/evaluation/real-tech-v1'
    with pytest.raises(ValueError, match='Explicit'):
        load_exploratory(root, allow_unverified=False)
    data, counts, metadata = load_exploratory(root, allow_unverified=True)
    assert counts['cases'] == 29 and counts['answerable'] == 24 and counts['negative'] == 5
    assert counts['chunks'] == 215
    assert 'VUE026' not in {q['id'] for q in data['cases']}
    assert all(q['review_status'] == 'unverified' and q['human_reviewed'] is False for q in data['cases'])
    assert metadata['human_gold'] is False and metadata['independent_final'] is False
    assert all(q['split'] == 'dev' and q['original_split'] == 'unassigned' for q in data['cases'])
