import copy
import json
import math
from pathlib import Path

import pytest

from scripts.evaluation.dataset import DEFAULT, generate, load, validate, write_json, sha
from scripts.evaluation.metrics import aggregate, retrieval_metrics
from scripts.evaluation.experiment import record
from scripts.evaluation.agent import argument_matches, score
from app.modules.rag.retrieval import RetrievedChunk
from uuid import UUID


def test_multiple_relevance_and_denominator():
    m = retrieval_metrics(['irrelevant','b','a'],['a','b','c'])
    assert m['recall@1']==0 and m['recall@3']==pytest.approx(2/3)
    assert m['hit_rate@3']==1 and m['mrr@10']==.5
    assert m['ndcg@10']==pytest.approx((1/math.log2(3)+1/math.log2(4))/(1+1/math.log2(3)+1/math.log2(4)))


def test_empty_and_duplicate_ranks_consume_slots():
    assert set(retrieval_metrics([],['a']).values())=={0}
    assert retrieval_metrics(['a'],[])=={}
    m = retrieval_metrics(['a','a','a','b'],['a','b','b'])
    assert m['recall@3']==.5 and m['recall@5']==1
    assert m['ndcg@10']==pytest.approx((1+1/math.log2(5))/(1+1/math.log2(3)))
    assert retrieval_metrics(['x']*10+['a'],['a'])['mrr@10']==0


def test_aggregate_negatives_latency_and_macro():
    rows = [dict(answerable=True,metrics=retrieval_metrics(['a'],['a','b']),ranked=['a'],latency_ms=10,scope_violations=[]),
            dict(answerable=True,metrics=retrieval_metrics([],['a']),ranked=[],latency_ms=20,scope_violations=[]),
            dict(answerable=False,metrics={},ranked=[],latency_ms=30,scope_violations=[])]
    s = aggregate(rows)
    assert s['metrics']['recall@1']==.25 and s['no_result_accuracy']==1
    assert s['answerable_false_empty_rate']==.5 and s['p50_ms']==20 and s['p95_ms']==29
    assert aggregate([])['p95_ms'] is None


def test_dataset_frozen_evidence_and_split():
    counts = validate()
    assert 300<=counts['chunks']<=1000 and counts['cases']==120
    assert counts['categories']==dict(exact=30,paraphrase=24,multi_evidence=24,distractor=18,unanswerable=12,boundary=12)
    data = load()
    for q in data['cases']:
        if q['category']=='multi_evidence':
            assert len(q['relevant_document_ids'])>=2


def test_deterministic_generation_and_reject_invalid_evidence(tmp_path):
    generate(tmp_path)
    assert (tmp_path/'dataset.json').read_bytes()==(DEFAULT/'dataset.json').read_bytes()
    data = load(tmp_path)
    q = next(q for q in data['cases'] if q['answerable'])
    q['evidence'][0]['quote']='this is not source evidence'
    write_json(tmp_path/'dataset.json',data)
    (tmp_path/'dataset.sha256').write_text(sha((tmp_path/'dataset.json').read_bytes()))
    with pytest.raises(ValueError,match='evidence'):
        validate(tmp_path)


def test_hash_rejects_edits(tmp_path):
    (tmp_path/'dataset.json').write_text('{}')
    (tmp_path/'dataset.sha256').write_text('wrong')
    with pytest.raises(ValueError,match='hash'):
        load(tmp_path)


def test_cross_tenant_rank_never_earns_credit():
    data = load()
    c = data['chunks'][0]
    case = dict(id='test',question='test',split='dev',category='boundary',answerable=True,
                tenant_id='foreign',knowledge_base_id=c['knowledge_base_id'],relevant_chunk_ids=[c['id']])
    row = RetrievedChunk(UUID(c['id']),UUID(c['document_id']),'test',0,c['content'],None,0.)
    result = record(case,'test',[row],.01,{c['id']:c},{'trace_id':'test'})
    assert result['scope_violations']==[c['id']] and result['metrics']['recall@10']==0 and result['failed']


def test_argument_semantics_and_order_are_not_just_schema():
    call = dict(name='search_knowledge_base',schema_valid=True,arguments={'query':'wrong entity','top_k':5})
    rule = dict(name='search_knowledge_base',equals={'query':'expected entity'},ranges={'top_k':[1,5]})
    assert not argument_matches(call,rule)
    case = {'expected':{'allowed_sequences':[['search_knowledge_base','get_document_info']],
                       'calls':[rule,{'name':'get_document_info'}],'finish_reason':'answer','error':None,
                       'executed_names':['search_knowledge_base','get_document_info'],'answer_contains':[]}}
    result = score(case,[dict(name='get_document_info',schema_valid=True,arguments={}),call],[],[],{'answer':'ok','finish_reason':'answer'},None)
    assert not result['ordered_sequence_pass'] and not result['task_success']


@pytest.mark.asyncio
async def test_all_agent_contracts_on_production_graph(config_env, tmp_path):
    from scripts.evaluation.agent import evaluate, FIXTURE
    result = await evaluate(FIXTURE,tmp_path/'agent.json')
    assert result['mode']=='scripted-graph-contract'
    assert result['summary']['task_success_rate']==1
    assert result['summary']['tool_argument_accuracy']<1  # deliberately injected bad calls
    for r in result['records']:
        assert r['trace_id'] and r['trace']['spans']
        if r['id']=='foreign_existing_document':
            assert r['final']['finish_reason']=='no_evidence'
