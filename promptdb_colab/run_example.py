"""Execute the supplied general-purpose Krea2 workflow through ComfyUI's API."""
import argparse
import copy
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

WIDGETS = {
    'UNETLoader': ('unet_name', 'weight_dtype'),
    'CLIPLoader': ('clip_name', 'type', 'device'),
    'VAELoader': ('vae_name',),
    'PromptDB': ('category', 'prompt_name', 'prompt_text', 'database'),
    'LayerUtility: TextJoinV2': ('delimiter',),
    'CLIPTextEncode': ('text',),
    'EmptyLatentImage': ('width', 'height', 'batch_size'),
    'SaveImage': ('filename_prefix',),
}


def prepare(workflow, size=256, steps=2):
    workflow = copy.deepcopy(workflow)
    nodes = {node['id']: node for node in workflow['nodes']}
    links = {link[0]: link for link in workflow['links']}

    def connection(link_id):
        link = links[link_id]
        source, slot = nodes[link[1]], link[2]
        if source.get('mode') == 2:
            return None
        if source.get('mode') == 4:
            candidates = [port for port in source.get('inputs', []) if port.get('link') is not None]
            if not candidates:
                return None
            port = candidates[min(slot, len(candidates) - 1)]
            return connection(port['link'])
        return [str(source['id']), slot]

    prompt = {}
    for node in workflow['nodes']:
        kind = node['type']
        if kind == 'MarkdownNote' or node.get('mode') in (2, 4):
            continue
        values = node.get('widgets_values') or []
        inputs = dict(zip(WIDGETS.get(kind, ()), values))
        if kind == 'KSampler':
            inputs = dict(zip(('seed', 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise'), [values[0], *values[2:]]))
            inputs.update(seed=123456789, steps=steps)
            node['widgets_values'][0] = 123456789
            node['widgets_values'][1] = 'fixed'
            node['widgets_values'][2] = steps
        elif kind == 'EmptyLatentImage':
            inputs.update(width=size, height=size, batch_size=1)
            node['widgets_values'][:3] = [size, size, 1]
        elif kind == 'SaveImage':
            inputs['filename_prefix'] = 'Krea2_PromptDB_Colab_Acceptance'
            node['widgets_values'] = [inputs['filename_prefix']]
        for port in node.get('inputs', []):
            if port.get('link') is not None:
                linked = connection(port['link'])
                if linked is not None:
                    inputs[port['name']] = linked
        prompt[str(node['id'])] = {'class_type': kind, 'inputs': inputs,
                                  '_meta': {'title': node.get('title', kind)}}
    return prompt, workflow


def request(endpoint, path, body=None):
    req = urllib.request.Request(endpoint.rstrip('/') + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(error.read().decode()) from error


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoint', default='http://127.0.0.1:8188')
    parser.add_argument('--size', type=int, default=256)
    parser.add_argument('--steps', type=int, default=2)
    args = parser.parse_args()
    workflow = json.loads((Path(__file__).parent / 'examples/workflows/Krea2_PromptDB_Example.json').read_text(encoding='utf-8'))
    prompt, workflow = prepare(workflow, args.size, args.steps)
    result = request(args.endpoint, '/prompt', {'prompt': prompt, 'extra_data': {'extra_pnginfo': {'workflow': workflow}}})
    if result.get('node_errors'):
        raise RuntimeError(json.dumps(result['node_errors'], ensure_ascii=False, indent=2))
    prompt_id = result['prompt_id']
    print('PROMPT_ID:', prompt_id, flush=True)
    Path('krea2_acceptance_job.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    for attempt in range(180):
        history = request(args.endpoint, '/history/' + prompt_id)
        if prompt_id in history:
            record = history[prompt_id]
            Path('krea2_acceptance_result.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps({'status': record.get('status'), 'outputs': record.get('outputs')}, ensure_ascii=True), flush=True)
            if record.get('status', {}).get('status_str') != 'success':
                raise RuntimeError('Generation did not succeed; inspect krea2_acceptance_result.json')
            if not record.get('outputs', {}).get('24', {}).get('images'):
                raise RuntimeError('No generated SaveImage output; this is not a successful image test')
            break
        if attempt % 6 == 0:
            print('Waiting for generation...', flush=True)
        time.sleep(5)
    else:
        raise TimeoutError(f'Generation still pending: {prompt_id}')
