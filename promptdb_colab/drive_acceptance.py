"""In-session acceptance for the user's existing Drive PromptDB workflow.

Call run(context) after start_services and before monitor. Never prints prompt
names, categories, text, workflow contents, rclone secrets, or public URLs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise RuntimeError('Acceptance support module is unavailable')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _call(path, body=None):
    req = urllib.request.Request('http://127.0.0.1:8188' + path,
        data=json.dumps(body).encode('utf-8') if body is not None else None,
        headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        # Do not echo API validation bodies: they can contain user prompt text.
        raise RuntimeError(f'ComfyUI API returned HTTP {error.code} for {path.split("?")[0]}') from None


def run(context):
    private = Path(context['private'])
    repo = Path(context['repo'])
    workflow_name = 'Krea2_Neutrino_PromptDB.json'
    workflow_path = private / 'workflows' / workflow_name
    if not workflow_path.is_file():
        raise RuntimeError('Original Drive Krea2 workflow is not present in the synced workspace')

    # Read original directly; content stays in process memory. Compare exact
    # bytes to ensure this is the Drive source, not a same-named seeded example.
    folder = str(context['drive_folder']).strip().strip('/')
    result = subprocess.run(['rclone', '--config', str(context['rclone_config']), 'cat',
        f'gdrive:{folder}/workflows/{workflow_name}'], capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError('Could not read original workflow from Google Drive')
    local_data = workflow_path.read_bytes()
    if hashlib.sha256(local_data).digest() != hashlib.sha256(result.stdout).digest():
        raise RuntimeError('The local workflow differs from the original Google Drive file')
    original = json.loads(local_data)
    print('Drive original workflow: exact byte match, valid JSON', flush=True)

    store = _module('acceptance_prompt_store', repo / 'promptdb_colab' / 'prompt_store.py')
    db_path = store.select_existing(private / 'user-db', 'krea2')
    if not db_path:
        raise RuntimeError('No existing Krea2 prompt database was selected from Drive')
    # Also prove the selected prompt database is the user's original Drive file,
    # not a local example, without printing its contents.
    try:
        db_relative = db_path.relative_to(private / 'user-db').as_posix()
    except ValueError:
        raise RuntimeError('Selected prompt database lies outside the synced Drive workspace') from None
    db_remote = subprocess.run(['rclone', '--config', str(context['rclone_config']), 'cat',
        f'gdrive:{folder}/user-db/{db_relative}'], capture_output=True, timeout=120)
    db_bytes = db_path.read_bytes()
    if db_remote.returncode or hashlib.sha256(db_bytes).digest() != hashlib.sha256(db_remote.stdout).digest():
        raise RuntimeError('The selected Krea2 database does not match the original Drive file')
    db = store.decode(db_bytes)
    candidate = next(((cat, name, text) for cat, bucket in db.items() if cat and isinstance(bucket, dict)
                      for name, text in bucket.items() if name and isinstance(text, str) and text), None)
    if candidate is None:
        raise RuntimeError('The synced Krea2 database has no usable prompt entry')
    cat, name, text = candidate
    if 'PromptDB' not in _call('/object_info/PromptDB'):
        raise RuntimeError('PromptDB node is not registered by ComfyUI')
    categories = _call('/prompt_db_categories', {'database': 'krea2'}).get('categories', [])
    prompts = _call('/prompt_db_prompts', {'database': 'krea2', 'category': cat}).get('prompts', [])
    actual = _call('/prompt_db_text', {'database': 'krea2', 'category': cat, 'prompt_name': name}).get('prompt_text')
    if cat not in categories or name not in prompts or actual != text:
        raise RuntimeError('PromptDB API does not match the selected synced Krea2 database')
    print('PromptDB: category, prompt lookup and text match the synced Drive database', flush=True)

    adapter = _module('acceptance_workflow_adapter', repo / 'promptdb_colab' / 'run_example.py')
    api, _ = adapter.prepare(original)
    nodes = {str(n['id']): n for n in original['nodes']}
    # Restore original image settings; prepare() normally uses small smoke-test defaults.
    for node_id, item in api.items():
        values = nodes[node_id].get('widgets_values') or []
        if item['class_type'] == 'KSampler':
            item['inputs']['seed'] = values[0]
            item['inputs']['steps'] = values[2]
        elif item['class_type'] == 'EmptyLatentImage':
            for field, value in zip(('width', 'height', 'batch_size'), values[:3]):
                if not isinstance(item['inputs'].get(field), list):
                    item['inputs'][field] = value
        elif item['class_type'] == 'SaveImage':
            item['inputs']['filename_prefix'] = 'validation/krea2-' + uuid.uuid4().hex

    # PreviewAny is an independent UI output; its history includes private
    # prompt text. Remove only disconnected previews from this in-memory copy.
    previews = {node_id for node_id, item in api.items() if item['class_type'] == 'PreviewAny'}
    for node_id, item in api.items():
        if node_id not in previews:
            for value in item.get('inputs', {}).values():
                if isinstance(value, list) and len(value) == 2 and str(value[0]) in previews:
                    raise RuntimeError('A preview node has a downstream dependency; cannot safely omit it')
    for node_id in previews:
        del api[node_id]

    submitted = _call('/prompt', {'prompt': api, 'client_id': str(uuid.uuid4())})
    prompt_id = submitted.get('prompt_id')
    if not prompt_id or submitted.get('node_errors'):
        raise RuntimeError('ComfyUI did not accept the original workflow graph')
    print('Original workflow copy submitted; settings preserved, preview output suppressed', flush=True)
    end = time.monotonic() + 900
    while time.monotonic() < end:
        record = _call('/history/' + prompt_id).get(prompt_id)
        if record:
            if record.get('status', {}).get('status_str') != 'success':
                raise RuntimeError('Original workflow did not complete successfully; inspect local ComfyUI log privately')
            images = [image for node in record.get('outputs', {}).values() for image in node.get('images', [])]
            if not images:
                raise RuntimeError('Original workflow produced no SaveImage output')
            image = images[0]
            filename = Path(image.get('filename', ''))
            subfolder = Path(image.get('subfolder', ''))
            if filename.name != str(filename) or subfolder.is_absolute() or '..' in subfolder.parts:
                raise RuntimeError('ComfyUI returned an unsafe output path')
            output = private / 'output' / subfolder / filename
            from PIL import Image
            with Image.open(output) as opened:
                size = opened.size
                opened.verify()
            latents = [item['inputs'] for item in api.values() if item['class_type'] == 'EmptyLatentImage']
            if len(latents) == 1:
                expected = (latents[0].get('width'), latents[0].get('height'))
                if all(isinstance(value, int) for value in expected) and size != expected:
                    raise RuntimeError('Generated image dimensions do not match the original workflow')
            print('Original workflow generated a decodable image:', size, flush=True)
            return {'prompt_id': prompt_id, 'output_path': str(output), 'size': size}
        time.sleep(3)
    raise TimeoutError('Original workflow did not finish within 15 minutes')
