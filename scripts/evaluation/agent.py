"""Isolated production LangGraph evaluation; all tools are mocks, no writes.

Default scripted backend measures graph contracts, NOT model intelligence.
--real uses the existing provider adapter but still isolated mock tools.
"""
import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from app.core.config import Settings
from app.modules.agent.backend import Call, Turn, DeepSeekAgentBackend, parse_arguments
from app.modules.agent.graph import Context, execute
from app.modules.agent.runtime import Capacity, Run
from app.modules.agent.schemas import SearchArgs, DocumentArgs, AgentError
from app.modules.rag.retrieval import RetrievedChunk
from app.observability.trace import capture
from scripts.evaluation.dataset import DEFAULT, load, write_json, sha
from scripts.evaluation.experiment import provenance

FIXTURE = DEFAULT / 'agent-cases.json'


def generate(path=FIXTURE):
    data = load()
    q = next(q for q in data['cases'] if q['answerable'] and q['split']=='dev')
    chunk = next(c for c in data['chunks'] if c['id']==q['relevant_chunk_ids'][0])
    foreign = next(d for d in data['documents'] if d['tenant_id']!=q['tenant_id'])
    doc_id = chunk['document_id']
    search = ['search_knowledge_base',{'query':q['entity'],'top_k':5}]
    info = ['get_document_info',{'document_id':doc_id}]
    def turn(*calls):
        return {'calls':[{'name':name,'arguments':args if isinstance(args,str) else json.dumps(args,ensure_ascii=False)} for name,args in calls], 'content':''}
    cases = []
    def add(name, turns, rules, finish='answer', error=None, tool_error=None, execution=None, final_text=None):
        if final_text is None:
            final_text = q['expected_answer']+' [S1]' if finish=='answer' else '文档状态 [S1]' if finish=='document_info' else '没有可用证据。'
        cases.append({'id':name,'input':q['question'] if finish=='answer' else '请查询该文档状态或说明证据不足：'+doc_id,
                      'tenant_id':q['tenant_id'],'knowledge_base_id':q['knowledge_base_id'], 'chunk_id':chunk['id'],
                      'expected':{'allowed_sequences':[[r['name'] for r in rules]],'calls':rules,'finish_reason':finish,
                                  'error':error, 'executed_names':execution if execution is not None else [r['name'] for r in rules if not r.get('expect_rejected')],
                                  'answer_contains':q['annotation']['required_quotes'] if finish=='answer' and not error else []},
                      'mock_tool_error':tool_error,'scripted_turns':turns+[{'calls':[],'content':final_text}]})
        cases[-1]['fault_injection'] = bool(tool_error or error or any(r.get('expect_rejected') for r in rules))
        cases[-1]['input'] = q['question']
    sr = {'name':'search_knowledge_base','contains':{'query':[q['entity']]},'ranges':{'top_k':[1,5]}}
    ir = {'name':'get_document_info','equals':{'document_id':doc_id}}
    add('search_fact',[turn(search)],[sr])
    add('document_status',[turn(info)],[ir],finish='document_info')
    add('search_then_document',[turn(search),turn(info)],[sr,ir])
    add('document_then_search',[turn(info),turn(search)],[ir,sr],final_text=q['expected_answer']+' [S2]')
    add('two_search_rounds',[turn(search),turn(search)],[sr,sr])
    for name, call in [
        ('tenant_injection',['search_knowledge_base',{'query':q['entity'],'top_k':5,'tenant_id':foreign['tenant_id']}]),
        ('kb_injection',['search_knowledge_base',{'query':q['entity'],'top_k':5,'knowledge_base_id':foreign['knowledge_base_id']}]),
        ('illegal_top_k',['search_knowledge_base',{'query':q['entity'],'top_k':100}]),
        ('malformed_json',['search_knowledge_base','{']),
        ('unknown_write_tool',['delete_document',{'document_id':doc_id}]),
    ]:
        code = 'invalid_tool' if name=='unknown_write_tool' else 'invalid_arguments'
        add(name,[turn(call)],[{'name':call[0],'expect_rejected':code}],finish='no_evidence',execution=[])
    add('foreign_existing_document',[turn(['get_document_info',{'document_id':foreign['id']}])],
        [{'name':'get_document_info','equals':{'document_id':foreign['id']}}],finish='no_evidence')
    for code in ('resource_not_found','unavailable','forbidden'):
        add('tool_'+code,[turn(search)],[sr],finish='no_evidence',error=code if code!='resource_not_found' else None,tool_error=code)
    add('invalid_citation',[turn(search)],[sr],error='invalid_citation',final_text='答案 [S999]')
    add('no_evidence',[],[],finish='no_evidence')
    cases[2]['input'] = f'先搜索{q["entity"]}的规定，再查看文档{doc_id}的状态，最后用正文作答。'
    cases[3]['input'] = f'先查看文档{doc_id}状态，再搜索{q["entity"]}的规定并回答。'
    cases[1]['input'] = '查询文档 '+doc_id+' 的状态。'
    cases[4]['input'] = f'分别搜索两次{q["entity"]}的规定，核对结果后作答。'
    cases[10]['input'] = '查询文档 '+foreign['id']+' 的状态。'
    cases[-1]['input'] = '你好，请说明需要什么信息才能查询知识库。'
    for case in cases:
        if any(r['name']=='search_knowledge_base' for r in case['expected']['calls']):
            case['input'] += '每次检索最多返回5条结果。'
    result = {'version':'agent-contract-v2.0','scope':'synthetic mock tools; no real writes; scripted fault injection is not model accuracy', 'cases':cases}
    write_json(path,result)
    path.with_suffix('.sha256').write_text(sha(path.read_bytes())+'\n',encoding='ascii')
    return result


class RecordingBackend:
    def __init__(self, backend):
        self.backend, self.calls = backend, []

    async def complete(self, *args):
        turn = await self.backend.complete(*args)
        for call in turn.calls:
            parsed, valid = None, False
            try:
                parsed = parse_arguments(call.arguments)
                schema = {'search_knowledge_base':SearchArgs,'get_document_info':DocumentArgs}[call.name]
                schema.model_validate(parsed)
                valid = True
            except (AgentError, ValidationError, KeyError):
                pass
            self.calls.append({'name':call.name,'raw_arguments':call.arguments,'arguments':parsed,'schema_valid':valid})
        return turn


class ScriptedBackend:
    def __init__(self, turns):
        self.turns, self.index = turns, 0

    async def complete(self, *args):
        row = self.turns[self.index]
        self.index += 1
        return Turn(row['content'],[Call(f'{self.index}-{i}',c['name'],c['arguments']) for i,c in enumerate(row['calls'])])


class IsolatedTools:
    def __init__(self, case, data):
        self.case, self.data, self.calls = case, data, []

    async def execute(self, name, args, sources):
        self.calls.append({'name':name,'arguments':args.model_dump(mode='json')})
        if self.case['mock_tool_error']:
            raise AgentError(self.case['mock_tool_error'])
        if name=='get_document_info':
            d = next((d for d in self.data['documents'] if d['id']==str(args.document_id) and all(d[k]==self.case[k] for k in ('tenant_id','knowledge_base_id'))),None)
            if d is None:
                raise AgentError('resource_not_found')
            return {'results':[sources.add('document',d['id'],dict(document_id=UUID(d['id']),filename=d['path'],snippet='{"status":"ready"}'),{'status':'ready'})]}
        c = next(c for c in self.data['chunks'] if c['id']==self.case['chunk_id'])
        if any(c[k]!=self.case[k] for k in ('tenant_id','knowledge_base_id')):
            raise AgentError('resource_not_found')
        # Canned evidence by scenario: tool-selection harness, not retrieval scoring.
        row = RetrievedChunk(UUID(c['id']),UUID(c['document_id']),'synthetic.md',c['chunk_index'],c['content'],c['metadata'],0.)
        return {'results':[sources.chunk(row)]}


def argument_matches(call, rule):
    if not call['schema_valid']:
        return False
    args = call['arguments']
    return all(args.get(k)==v for k,v in rule.get('equals',{}).items()) and all(type(args.get(k)) in (int,float) and lo<=args[k]<=hi for k,(lo,hi) in rule.get('ranges',{}).items()) and all(isinstance(args.get(k),str) and all(v in args[k] for v in values) for k,values in rule.get('contains',{}).items())


def score(case, calls, executed, events, final, error):
    expected = case['expected']
    names = [c['name'] for c in calls]
    selection = any(Counter(names)==Counter(sequence) for sequence in expected['allowed_sequences'])
    ordered = names in expected['allowed_sequences']
    correct = [argument_matches(c,expected['calls'][i]) if i<len(expected['calls']) and c['name']==expected['calls'][i]['name'] else False for i,c in enumerate(calls)]
    # Controlled faults count as invalid arguments, but expected rejection can pass contract.
    rejection_checks = []
    for i, rule in enumerate(expected['calls']):
        if rule.get('expect_rejected'):
            code = rule['expect_rejected']
            rejection_checks.append(i<len(calls) and not calls[i]['schema_valid'] and
                                    (code=='invalid_tool' or any(e['data'].get('error_code')==code for e in events)))
    args_contract = all(correct[i] if not rule.get('expect_rejected') else True for i,rule in enumerate(expected['calls']) if i<len(calls)) and len(calls)==len(expected['calls'])
    finish = error==expected['error'] and (bool(error) or final is not None and final['finish_reason']==expected['finish_reason'] and all(s in final['answer'] for s in expected['answer_contains']))
    executed_ok = [c['name'] for c in executed]==expected['executed_names']
    return {'tool_selection_pass':selection, 'argument_correct':sum(correct),'argument_attempts':len(calls),
            'ordered_sequence_pass':ordered,'expected_fault_handling_pass':all(rejection_checks) if rejection_checks else None,
            'task_success':bool(selection and ordered and args_contract and all(rejection_checks) and finish and executed_ok)}


def summarize_records(report):
    records = report['records']
    real = report['mode']=='real-model-mock-tools'
    infrastructure = [r for r in records if real and r['error'] in ('unavailable','timeout') and not r['calls']]
    eligible = [r for r in records if r not in infrastructure]
    n, attempts = len(eligible), sum(r['scores']['argument_attempts'] for r in eligible)
    report['summary'] = {'attempted_n':len(records),'n':n,'infrastructure_failed_n':len(infrastructure),
                         'operational_completion_rate':sum(r['error'] is None for r in records)/len(records) if records else None,
                         'tool_selection_accuracy':sum(r['scores']['tool_selection_pass'] for r in eligible)/n if n else None,
                         'ordered_sequence_accuracy':sum(r['scores']['ordered_sequence_pass'] for r in eligible)/n if n else None,
                         'argument_correct':sum(r['scores']['argument_correct'] for r in eligible),'argument_attempts':attempts,
                         'tool_argument_accuracy':sum(r['scores']['argument_correct'] for r in eligible)/attempts if attempts else None,
                         'task_success_rate':sum(r['scores']['task_success'] for r in eligible)/n if n else None}
    report['status'] = 'infrastructure_failed' if records and len(infrastructure)==len(records) else 'partial_infrastructure_failure' if infrastructure else 'complete'
    return report


def save_report(report, output):
    write_json(output,report)
    lines = ['# Agent evaluation','',f"Mode: {report['mode']}; status: {report['status']}",'',report['scope'],'',
             'Scripted metrics measure graph contracts, not model quality. Argument accuracy requires schema AND scenario rules (entity containment, exact document identity, numeric range). Selection compares tool multisets; order compares full sequences. Task success checks order, arguments, rejected faults, executed calls, expected errors and final behavior. Final factual answers use a closed-fact lexical proxy, not a semantic judge.', '',
             'Provider unavailable/timeout before any call is an infrastructure failure: included in attempted/availability counts and excluded from capability denominators. Injected graph faults remain in scripted denominators. No-call argument accuracy is N/A.', '',
             '```json',json.dumps(report.get('summary',{}),ensure_ascii=False,indent=2),'```','',
             '| Case | Error | Task contract passed | Local trace ID |','| --- | --- | --- | --- |']
    for r in report['records']:
        lines.append(f"| {r['id']} | {r['error'] or '-'} | {r['scores']['task_success']} | {r['trace_id']} |")
    output.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


async def evaluate(path, output, real=False):
    raw = path.read_bytes()
    if sha(raw)!=path.with_suffix('.sha256').read_text().strip():
        raise ValueError('Frozen agent fixture hash mismatch')
    fixture, data, settings = json.loads(raw), load(), Settings()
    if real and (settings.llm_base_url.rstrip('/')!='https://api.deepseek.com' or not settings.deepseek_api_key):
        raise ValueError('Real evaluation requires configured approved DeepSeek endpoint/key')
    report = {**provenance(DEFAULT),'version':fixture['version'],'agent_dataset_sha256':sha(raw),
              'mode':'real-model-mock-tools' if real else 'scripted-graph-contract',
              'scope':fixture['scope'],'status':'running','records':[],'langsmith_uploaded':False,
              'llm_model':settings.llm_model if real else None,'model_timeout_seconds':settings.agent_model_timeout_seconds,
              'tool_timeout_seconds':settings.agent_tool_timeout_seconds}
    output.parent.mkdir(parents=True,exist_ok=True)
    for case in fixture['cases']:
        if real and case['fault_injection']:
            continue  # Provider quality cannot be measured by forcing scripted invalid calls.
        backend = RecordingBackend(DeepSeekAgentBackend(settings) if real else ScriptedBackend(case['scripted_turns']))
        tools = IsolatedTools(case,data)
        events, final, error = [], None, None
        async def emit(event, payload):
            events.append({'event':event,'data':json.loads(json.dumps(payload,default=str))})
        pool = Capacity(); pool.acquire(1)
        run = Run(settings.agent_timeout_seconds,pool)
        with capture() as trace:
            try:
                state = await execute(Context(run,settings,backend,tools,emit),case['input'])
                final = state['final']
            except AgentError as exc:
                error = exc.code
            except TimeoutError:
                error = 'timeout'
            finally:
                run.close()
                if run.jobs: await asyncio.gather(*run.jobs,return_exceptions=True)
        row = {'id':case['id'],'input':case['input'],'expected':case['expected'],'calls':backend.calls,'executed_calls':tools.calls,
               'events':events,'final':final,'error':error,'trace_id':trace.id,'trace':trace.summary(),
               'scores':score(case,backend.calls,tools.calls,events,final,error)}
        report['records'].append(row)
        write_json(output,report)
    report['finished_at']=datetime.now(timezone.utc).isoformat()
    summarize_records(report)
    save_report(report,output)
    return report


if __name__=='__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['generate','run','report'])
    p.add_argument('--fixture',type=Path,default=FIXTURE)
    p.add_argument('--output',type=Path,default=Path('docs/evaluation/v2/agent-contract.json'))
    p.add_argument('--real',action='store_true')
    a = p.parse_args()
    if a.action=='generate':
        print('cases',len(generate(a.fixture)['cases']))
    elif a.action=='report':
        save_report(summarize_records(json.loads(a.output.read_text(encoding='utf-8'))),a.output)
    else:
        print(json.dumps(asyncio.run(evaluate(a.fixture,a.output,a.real))['summary'],indent=2))
