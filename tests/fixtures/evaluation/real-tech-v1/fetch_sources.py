"""Fetch only the selected Vue 3 Chinese Markdown and repository notices."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent
REPOSITORY = 'https://github.com/vuejs-translations/docs-zh-cn'
PATHS = [
    'src/guide/essentials/reactivity-fundamentals.md',
    'src/guide/essentials/computed.md',
    'src/guide/essentials/watchers.md',
    'src/guide/essentials/lifecycle.md',
    'src/guide/essentials/template-refs.md',
    'src/guide/essentials/component-basics.md',
    'src/guide/components/props.md',
    'src/guide/components/events.md',
    'src/guide/components/v-model.md',
    'src/guide/components/attrs.md',
    'src/guide/components/slots.md',
    'src/guide/components/provide-inject.md',
    'src/guide/reusability/composables.md',
    'src/guide/extras/reactivity-in-depth.md',
    'src/api/reactivity-core.md',
]


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'real-tech-v1-corpus-preparation'})
    with urllib.request.urlopen(request, timeout=40) as response:
        return response.read()


def main():
    target = ROOT / 'upstream.json'
    if target.exists():
        raise SystemExit('Refusing to overwrite an existing source snapshot')
    # Pinned from read-only `git ls-remote ... refs/heads/main`.
    # Avoid GitHub's anonymous API quota; every download uses this immutable SHA.
    revision = '418f5ae6e15c7a90beae017e44d58dac3d93ad95'
    files = []
    for source_path in ['LICENSE', 'README.md', *PATHS]:
        url = f'https://raw.githubusercontent.com/vuejs-translations/docs-zh-cn/{revision}/{source_path}'
        raw = fetch(url)
        local = ROOT / ('licenses/upstream-LICENSE.txt' if source_path == 'LICENSE' else 'corpus/' + source_path if source_path in PATHS else 'licenses/upstream-README.md')
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(raw)
        files.append({'source_path': source_path, 'local_path': local.relative_to(ROOT).as_posix(),
                      'source_url': f'{REPOSITORY}/blob/{revision}/{source_path}', 'raw_url': url,
                      'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
    result = {'repository': REPOSITORY, 'commit': revision,
              'revision_resolution': 'git ls-remote refs/heads/main',
              'retrieved_at': datetime.now(timezone.utc).isoformat(), 'files': files}
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'commit': revision, 'files': len(files)}))


if __name__ == '__main__':
    main()
