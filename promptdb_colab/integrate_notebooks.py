"""Add PromptDB before upstream launch without rewriting upstream program logic."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "# BEGIN COLAB PROMPTDB INTEGRATION\n"
END = "# END COLAB PROMPTDB INTEGRATION\n"
HOOK = BEGIN + "install_colab_promptdb()\n" + END + "\n"
STORAGE_HOOK = BEGIN + "configure_colab_model_storage()\n" + END + "\n"
CONFIG = '''# @title PromptDB：安裝與私人 Drive 選項（先執行）
promptdb_use_drive = False # @param {type:"boolean"}
models_use_drive = False # @param {type:"boolean"}
promptdb_drive_folder = "/content/drive/MyDrive/ComfyUI-PromptDB" # @param {type:"string"}

from pathlib import Path as _PromptDBPath
import subprocess as _promptdb_subprocess
import importlib.util as _promptdb_importlib

def _promptdb_helper():
    repository = _PromptDBPath('/content/Google-Colab_Notebooks')
    if not repository.exists():
        _promptdb_subprocess.run([
            'git', 'clone', '--branch', 'codex/colab-promptdb', '--single-branch',
            'https://github.com/JackChen6203/Google-Colab_Notebooks.git', str(repository)
        ], check=True)
    spec = _promptdb_importlib.spec_from_file_location(
        'colab_promptdb_setup', repository / 'promptdb_colab/setup.py')
    helper = _promptdb_importlib.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper

def configure_colab_model_storage():
    if models_use_drive:
        from google.colab import drive
        drive.mount('/content/drive')
        helper = _promptdb_helper()
        helper.configure_model_cache('/content/ComfyUI', _PromptDBPath(promptdb_drive_folder) / 'models')
        print('Model downloads and loading now use persistent Google Drive storage.')

def install_colab_promptdb():
    helper = _promptdb_helper()
    data = None
    if promptdb_use_drive:
        from google.colab import drive
        drive.mount('/content/drive')
        data = _PromptDBPath(promptdb_drive_folder) / 'user-db'
        if not data.is_dir():
            raise FileNotFoundError(f'Create {data} and add prompt JSON files first')
    helper.install('/content/ComfyUI', data)
    if promptdb_use_drive:
        helper.import_workflows('/content/ComfyUI', _PromptDBPath(promptdb_drive_folder) / 'workflows')
        manifest = _PromptDBPath(promptdb_drive_folder) / 'models.json'
        if manifest.is_file():
            helper.download_models('/content/ComfyUI', manifest)
    print('PromptDB installed before ComfyUI startup. Original model and launch settings follow.')
'''


def integrate(notebook, direct=False):
    notebook['cells'] = [c for c in notebook['cells'] if c.get('id') != 'promptdb-options']
    for cell in notebook['cells']:
        if cell['cell_type'] == 'code':
            source = ''.join(cell['source'])
            source = re.sub(r'# BEGIN COLAB PROMPTDB INTEGRATION\n.*?# END COLAB PROMPTDB INTEGRATION\n\n', '', source, flags=re.S)
            cell['source'] = source.splitlines(keepends=True)
    inserted = False
    for cell in notebook['cells']:
        if cell['cell_type'] != 'code':
            continue
        source = ''.join(cell['source'])
        storage = re.search(r'^def (?:download_\w+|model_download\w*|pull)\(', source, flags=re.M)
        if storage:
            source = source[:storage.start()] + STORAGE_HOOK + source[storage.start():]
        if direct:
            if 'Environment Setup Complete' in source:
                source = source.rstrip() + '\n\n' + HOOK
                inserted = True
        else:
            match = re.search(r'^use_cloudflare\s*=', source, flags=re.M)
            if match:
                source = source[:match.start()] + HOOK + source[match.start():]
                inserted = True
        cell['source'] = source.splitlines(keepends=True)
    if not inserted:
        raise ValueError('No supported pre-launch installation point')
    notebook['cells'].insert(1, {
        'cell_type': 'code', 'id': 'promptdb-options',
        'metadata': {'cellView': 'form'}, 'source': CONFIG.splitlines(keepends=True),
        'execution_count': None, 'outputs': []})
    if direct:
        for cell in notebook['cells']:
            source = ''.join(cell['source'])
            marker = 'conditioning = clip_text_encode.encode('
            if marker in source:
                extra = BEGIN + '''# Optional database selection for the original notebook generation interface.
promptdb_database = "krea2" # @param ["krea2", "illustrious"]
promptdb_category = "" # @param {type:"string"}
promptdb_name = "" # @param {type:"string"}
if promptdb_category and promptdb_name:
    import json as _promptdb_json
    _db_name = 'prompts_krea2.json' if promptdb_database == 'krea2' else 'prompts.json'
    _db = _promptdb_json.loads((_PromptDBPath('/content/ComfyUI/user/default/user-db') / _db_name).read_text(encoding='utf-8-sig'))
    your_prompt = _db[promptdb_category][promptdb_name]
''' + END + '\n'
                cell['source'] = source.replace(marker, extra + marker, 1).splitlines(keepends=True)
    return notebook


if __name__ == '__main__':
    for path in sorted((ROOT / 'ComfyUI').rglob('*.ipynb')):
        notebook = json.loads(path.read_text(encoding='utf-8'))
        integrate(notebook, direct=path.parent.name == 'Z_Image')
        path.write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(path.relative_to(ROOT))
    # The main entry now uses a full upstream ComfyUI UI notebook.
    source = ROOT / 'ComfyUI/ComfyUI_Flux1Dev_USO/ComfyUI_Flux1Dev_USO.ipynb'
    (ROOT / 'ComfyUI_PromptDB.ipynb').write_bytes(source.read_bytes())
