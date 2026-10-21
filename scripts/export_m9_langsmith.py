"""Explicit, offline whitelist export. No automatic tracing or payload capture."""
import argparse
import json
import os
from pathlib import Path
from uuid import uuid4
from app.observability.trace import NAMES, ERRORS


def sanitized(record: dict) -> dict:
    spans = []
    for source in record.get('spans', [])[:128]:
        if source.get('name') not in NAMES:
            continue
        target = {'name': source['name']}
        for key in ('duration_ms','start_ms'):
            value = source.get(key)
            import math
            if type(value) in (float,int) and math.isfinite(value) and value>=0:
                target[key] = value
        status = source.get('status')
        if status in ('ok','error','cancelled'):target['status']=status
        error = source.get('error_code')
        if isinstance(error,str) and error in ERRORS:target['error_code']=error
        usage=source.get('usage')
        if isinstance(usage,dict):
            keys=('prompt_tokens','completion_tokens','total_tokens')
            if all(type(usage.get(k)) is int and usage[k]>=0 for k in keys):
                target['usage']={k:usage[k] for k in keys}
        spans.append(target)
    # Never forward original trace IDs, metadata, arbitrary nested fields or timestamps.
    return {'schema_version':1,'spans':spans}


def export(records: list[dict], client, project: str) -> None:
    for record in records:
        client.create_run(name='M9 sanitized evaluation',run_type='chain',inputs={},
                          outputs=sanitized(record),project_name=project,id=uuid4())


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    parser.add_argument('--send',action='store_true')
    args=parser.parse_args()
    records=[row['trace'] for row in json.loads(args.run.read_text(encoding='utf-8'))['records']]
    if not args.send:
        print(json.dumps([sanitized(r) for r in records],indent=2))
    else:
        if not os.environ.get('LANGSMITH_API_KEY'):
            parser.error('Explicit LANGSMITH_API_KEY required; no upload performed')
        from langsmith import Client
        with Client(api_key=os.environ['LANGSMITH_API_KEY'],api_url='https://api.smith.langchain.com',auto_batch_tracing=False) as client:
            export(records,client,'m9-sanitized-evaluation')
