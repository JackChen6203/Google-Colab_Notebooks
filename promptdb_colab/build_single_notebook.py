"""Build the primary all-in-one Krea2 + Drive + Cloudflare entry."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cells = []


def cell(kind, source):
    value = {'cell_type': kind, 'id': f'krea2-single-{len(cells)}', 'metadata': {}, 'source': source.splitlines(True)}
    if kind == 'code':
        compile(source, '<notebook>', 'exec')
        value.update(execution_count=None, outputs=[])
    cells.append(value)


cell('markdown', '''# Krea2 PromptDB — Google Drive + Cloudflare
依序執行，或選「全部執行」。首次 Google Drive 掛載須自行授權。
預設從 Drive 自動載入 `prompt_defalut.json`；首次沒有檔案時使用一般旅拍範例。
勾選 upload_prompt 可上傳一般用途 JSON，保存在 Drive，下次不用重傳。
Cloudflare 連結公開此 runtime 的 ComfyUI；停止 runtime 後網址失效。
''')
cell('code', '''# @title 1. 選項與環境安裝
upload_prompt = False # @param {type:"boolean"}
upload_illustrious_prompt = False # @param {type:"boolean"}
upload_workflows = False # @param {type:"boolean"}
upload_illustrious_checkpoint = False # @param {type:"boolean"}
store_models_on_drive = True # @param {type:"boolean"}
download_krea2_models = True # @param {type:"boolean"}
drive_folder = "/content/drive/MyDrive/ComfyUI-PromptDB" # @param {type:"string"}
from pathlib import Path
import subprocess, sys, importlib.util, json
from google.colab import drive, files
drive.mount('/content/drive')
PRIVATE = Path(drive_folder)
PRIVATE.mkdir(parents=True, exist_ok=True)
REPO = Path('/content/Google-Colab_Notebooks')
COMFY = Path('/content/ComfyUI')
def run(*args):
    subprocess.run([str(arg) for arg in args], check=True)
if not REPO.exists():
    run('git', 'clone', '--branch', 'codex/colab-promptdb', '--single-branch', 'https://github.com/JackChen6203/Google-Colab_Notebooks.git', REPO)
else:
    run('git', '-C', REPO, 'pull', '--ff-only')
if not COMFY.exists():
    run('git', 'clone', 'https://github.com/Comfy-Org/ComfyUI.git', COMFY)
run(sys.executable, '-m', 'pip', 'install', '-r', COMFY / 'requirements.txt')
def module(name):
    spec = importlib.util.spec_from_file_location(name, REPO / 'promptdb_colab' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result
setup = module('setup')
store = module('prompt_store')
if store_models_on_drive:
    setup.configure_model_cache(COMFY, PRIVATE / 'models')
''')
cell('code', '''# @title 2. 上傳或自動載入 Drive 提示庫
setup.install(COMFY, preserve_existing=True)
def persistent_database(database, upload, default_name):
    selection_file = PRIVATE / ('active_prompt_' + database + '.json')
    folder = PRIVATE / 'user-db' / database
    if upload:
        uploaded = files.upload()
        if len(uploaded) != 1:
            raise ValueError('Choose exactly one JSON for ' + database)
        filename, content = next(iter(uploaded.items()))
        selected = store.save_upload(folder, filename, content)
        selection_file.write_text(json.dumps({'filename': filename}), encoding='utf-8')
    elif selection_file.is_file():
        filename = json.loads(selection_file.read_text(encoding='utf-8'))['filename']
        if Path(filename).name != filename or '/' in filename or chr(92) in filename:
            raise ValueError('Invalid saved filename')
        selected = folder / filename
    else:
        selected = folder / default_name
        if not selected.exists():
            example = 'prompts_krea2.json' if database == 'krea2' else 'prompts.json'
            store.save_upload(folder, default_name, (REPO / 'promptdb_colab/examples' / example).read_bytes())
    store.activate(COMFY, selected, database)
    print(database, 'persistent database:', selected)
persistent_database('illustrious', upload_illustrious_prompt, 'prompts.json')
selection = PRIVATE / 'active_prompt.json'
if upload_prompt:
    uploaded = files.upload()
    if len(uploaded) != 1:
        raise ValueError('Choose exactly one prompt JSON file')
    filename, content = next(iter(uploaded.items()))
    source = store.save_upload(PRIVATE / 'user-db', filename, content)
    selection.write_text(json.dumps({'filename': filename}), encoding='utf-8')
elif selection.is_file():
    filename = json.loads(selection.read_text(encoding='utf-8'))['filename']
    if Path(filename).name != filename or '/' in filename or '\\\\' in filename:
        raise ValueError('Invalid saved prompt filename')
    source = PRIVATE / 'user-db' / filename
else:
    source = PRIVATE / 'user-db/prompt_defalut.json'
    if not source.exists():
        store.save_upload(source.parent, source.name, (REPO / 'promptdb_colab/examples/prompts_krea2.json').read_bytes())
setup.install(COMFY, preserve_existing=True)
store.activate(COMFY, source, 'krea2')
setup.configure_web_navigation(COMFY)
setup.import_workflows(COMFY, PRIVATE / 'workflows')
if upload_workflows:
    uploaded = files.upload()
    for filename, content in uploaded.items():
        if Path(filename).name != filename or '/' in filename or chr(92) in filename or not filename.lower().endswith('.json'):
            raise ValueError('Choose UI workflow JSON files')
        value = json.loads(content.decode('utf-8-sig'))
        if not isinstance(value, dict) or not isinstance(value.get('nodes'), list):
            raise ValueError('Expected ComfyUI UI workflow: ' + filename)
        target = PRIVATE / 'workflows' / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != content:
            raise FileExistsError('Rename the upload to preserve existing workflow: ' + filename)
        target.write_bytes(content)
    setup.import_workflows(COMFY, PRIVATE / 'workflows')
if upload_illustrious_checkpoint:
    print('Upload a general-purpose safetensors checkpoint; large files are better copied directly to Drive models/checkpoints.')
    uploaded = files.upload()
    for filename, content in uploaded.items():
        if Path(filename).name != filename or '/' in filename or chr(92) in filename or not filename.lower().endswith('.safetensors'):
            raise ValueError('Expected a safetensors filename')
        target = PRIVATE / 'models/checkpoints' / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise FileExistsError('Existing checkpoint preserved: ' + filename)
        target.write_bytes(content)
    if not store_models_on_drive:
        raise ValueError('Enable store_models_on_drive to load uploaded checkpoint files')
if download_krea2_models:
    setup.download_models(COMFY, REPO / 'promptdb_colab/models.krea2.json')
print('Active persistent PromptDB:', source)
print('Workflow: PromptDB-Drive/Krea2_PromptDB_Quick_Test')
''')
cell('code', '''# @title 3. 啟動 ComfyUI 與 Cloudflare Tunnel
import shutil, urllib.request, runpy
from IPython.display import display, HTML
if not shutil.which('cloudflared'):
    package = Path('/content/cloudflared.deb')
    urllib.request.urlretrieve('https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb', package)
    run('dpkg', '-i', package)
resume = module('resume_test')
resume.main(verify_sample=False)
log = Path('/content/cloudflare-resume.log').read_text()
import re, html
url = re.search(r'https://[a-z]+(?:-[a-z]+)+\\.trycloudflare\\.com', log).group(0)
display(HTML('<a target="_blank" href="' + html.escape(url, quote=True) + '">開啟 ComfyUI</a>'))
print('首次請選工作流程 → PromptDB-Drive → Krea2_PromptDB_Quick_Test，再按執行。')
''')
notebook = {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'accelerator': 'GPU', 'colab': {'gpuType': 'T4', 'provenance': []}, 'kernelspec': {'name': 'python3', 'display_name': 'Python 3'}, 'language_info': {'name': 'python'}}, 'cells': cells}
(ROOT / 'ComfyUI_PromptDB.ipynb').write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
