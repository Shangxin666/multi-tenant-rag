import asyncio
import json
from types import SimpleNamespace
import pytest
from app.observability import trace as t
from scripts.evaluation.scoring import retrieval, rule_score, reviewed_score, digest, summarize
from scripts.evaluate_m9 import load_dataset


@pytest.mark.parametrize('ranked,relevant,k,recall,mrr',[
    (['a','b'],['b'],1,0,0),(['a','b'],['b'],2,1,.5),
    (['a','a','b'],['a','b'],2,1,1),([],['a'],5,0,0),(['a'],[],5,None,None)])
def test_metrics(ranked,relevant,k,recall,mrr):
    assert retrieval(ranked,relevant,k)=={'recall':recall,'mrr':mrr}


def test_frozen_dataset_splits():
    dataset=load_dataset()
    assert dataset['version']=='m9-artificial-v1'
    assert len(dataset['cases'])==36
    for mode in ('rag','agent'):
        assert {c['split'] for c in dataset['cases'] if c['mode']==mode}=={'dev','holdout'}


def test_rules_are_not_semantic_judgment():
    case={'mode':'rag','facts':[['12','十二']],'no_answer':False}
    scored=rule_score(case,'不是12天 [S1]',{'S1':'12天'},[])
    assert scored['answer_rule_pass']  # Intentional documented false positive: lexical rules lack negation.
    assert reviewed_score({},None)['faithfulness'] is None
    assert not rule_score(case,'12天 [S2]',{'S1':'12天'},[])['citation_ids_valid']


def test_reviews_only_actual_context_and_provenance():
    record={'answer':'年假12天 [S1]','evidence':{'S1':'正式员工年假12天'},'case_id':'x'}
    review={'record_hash':digest(record),'reviewer_type':'human','reviewer':'test fixture',
        'correctness':1,'task_completed':True,'rationale':'fixture only',
        'claims':[{'text':'年假12天','verdict':'supported','source_id':'S1','quote':'年假12天'}]}
    assert reviewed_score(record,review)['faithfulness']==1
    review['claims'][0]['quote']='source not supplied to model'
    with pytest.raises(ValueError):reviewed_score(record,review)
    review['record_hash']='stale'
    with pytest.raises(ValueError):reviewed_score(record,review)


def test_no_claims_not_automatic_full_credit():
    record={'answer':'资料不足','evidence':{}}
    review={'record_hash':digest(record),'reviewer_type':'model_assisted','reviewer':'fixture',
            'correctness':1,'task_completed':True,'rationale':'refusal','claims':[]}
    assert reviewed_score(record,review)['faithfulness'] is None


@pytest.mark.parametrize('calls,expected',[
    ([{'name':'search_knowledge_base','valid':True}],True),
    ([{'name':'search_knowledge_base','valid':False}],False),
    ([{'name':'unknown','valid':False}],False),([],False)])
def test_agent_completion(calls,expected):
    case={'mode':'agent','facts':[['12']],'no_answer':False,'allowed_tools':['search_knowledge_base'],'required_tools':['search_knowledge_base']}
    assert rule_score(case,'12天[S1]',{'S1':'12天'},calls)['task_rule_pass']==expected


def test_trace_usage_whitelist_and_missing():
    with t.capture() as trace:
        with t.span('llm'):
            t.usage(SimpleNamespace(prompt_tokens=3,completion_tokens=2,total_tokens=5))
            t.usage(SimpleNamespace(prompt_tokens=3,completion_tokens=2,total_tokens=5))
            t.count(password='SECRET',candidates=3)
        with t.span('llm'):pass
    result=trace.summary()
    assert result['usage']['total_tokens']==5 and not result['usage']['complete']
    assert result['usage']['reported_calls']==1
    assert 'SECRET' not in json.dumps(result)


@pytest.mark.parametrize('values',[(1,2,4),(-1,1,0),(True,1,2),(1,None,1)])
def test_invalid_usage_unknown(values):
    with t.capture() as trace:
        with t.span('llm'):
            t.usage(SimpleNamespace(**dict(zip(('prompt_tokens','completion_tokens','total_tokens'),values))))
    assert trace.summary()['usage']['reported_calls']==0


@pytest.mark.asyncio
async def test_context_isolation_parent_and_cancel():
    async def task(cancel=False):
        with t.capture() as trace:
            try:
                with t.span('agent.run'):
                    with t.span('tool'):
                        await asyncio.sleep(0)
                        if cancel:raise asyncio.CancelledError()
            except asyncio.CancelledError:pass
        return trace.summary()
    a,b=await asyncio.gather(task(),task(True))
    assert a['trace_id']!=b['trace_id']
    assert b['spans'][1]['parent_span_id']==b['spans'][0]['span_id']
    assert b['spans'][0]['status']=='cancelled'
    assert a['spans'][0]['status']=='ok' and t.active.get() is None


@pytest.mark.asyncio
async def test_sink_failure_and_exception_redaction(monkeypatch):
    def broken(record):raise OSError('SECRET')
    monkeypatch.setattr(t,'_sink',broken)
    @t.traced('rag.query',root=True)
    async def call():return 42
    assert await call()==42
    with t.capture() as trace:
        with pytest.raises(RuntimeError),t.span('tool'):
            raise RuntimeError('SECRET document body')
    assert 'SECRET' not in json.dumps(trace.summary())


def test_bound_and_closed_trace(tmp_path):
    with t.capture() as trace:
        for _ in range(140):
            with t.span('tool'):pass
    assert len(trace.spans)==128 and trace.dropped==12
    t.configure(tmp_path/'safe.jsonl');t.configure(None)


def test_summary_separates_unreviewed():
    record={'split':'holdout','mode':'rag','case_id':'x','error':None,'rules':{'task_rule_pass':True}}
    result=summarize([record])['holdout/rag']
    assert result['unreviewed']==1 and result['human/faithfulness']=={'n':0,'mean':None}
