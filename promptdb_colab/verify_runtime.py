"""Verify live ComfyUI registration and sample PromptDB API text (no generation)."""
import argparse
import json
import urllib.request
from pathlib import Path


def verify(endpoint):
    root = Path(__file__).parent
    workflow = json.loads((root / 'examples/workflows/Krea2_PromptDB_Example.json').read_text(encoding='utf-8'))
    endpoint = endpoint.rstrip('/')
    with urllib.request.urlopen(endpoint + '/object_info', timeout=15) as response:
        nodes = json.load(response)
    needed = {node['type'] for node in workflow['nodes']} - {'MarkdownNote'}
    missing = sorted(needed - nodes.keys())
    if missing:
        raise RuntimeError(f'Missing runtime node classes: {missing}')
    db = json.loads((root / 'examples/prompts_krea2.json').read_text(encoding='utf-8'))
    checked = 0
    for node in workflow['nodes']:
        if node['type'] != 'PromptDB':
            continue
        category, name, _, database = node['widgets_values']
        request = urllib.request.Request(endpoint + '/prompt_db_text',
            data=json.dumps({'category': category, 'prompt_name': name, 'database': database}).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=15) as response:
            actual = json.load(response)['prompt_text']
        if actual != db[category][name]:
            raise RuntimeError(f'Sample prompt does not match runtime database: {category}/{name}')
        checked += 1
    return {'registered_backend_node_types': sorted(needed), 'sample_prompt_checks': checked,
            'workflow_node_count': len(workflow['nodes']), 'generation_tested': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', default='http://127.0.0.1:8188')
    args = parser.parse_args()
    print(json.dumps(verify(args.endpoint), ensure_ascii=False, indent=2))
