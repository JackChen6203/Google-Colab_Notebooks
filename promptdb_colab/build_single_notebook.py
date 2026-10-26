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
提示庫、工作流與自行上傳的模型一律從 Drive 讀取，不會跳出選檔視窗。
Cloudflare 連結公開此 runtime 的 ComfyUI；停止 runtime 後網址失效。
''')
cell('code', '''# @title 1. 選項與環境安裝
store_models_on_drive = True # @param {type:"boolean"}
download_krea2_models = True # @param {type:"boolean"}
drive_folder = "/content/drive/MyDrive/ComfyUI-PromptDB" # @param {type:"string"}
from pathlib import Path
import subprocess, sys, importlib.util, json
from google.colab import drive
drive.mount('/content/drive')
PRIVATE = Path(drive_folder)
PRIVATE.mkdir(parents=True, exist_ok=True)
for relative in ('models/checkpoints', 'models/diffusion_models', 'models/text_encoders', 'models/vae', 'models/loras', 'workflows', 'user-db/illustrious'):
    (PRIVATE / relative).mkdir(parents=True, exist_ok=True)
print('Drive folders ready:', PRIVATE)
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
def module(name):
    spec = importlib.util.spec_from_file_location(name, REPO / 'promptdb_colab' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result
setup = module('setup')
store = module('prompt_store')
for filename in ('prompts.json', 'prompts_krea2.json'):
    destination = PRIVATE / 'user-db' / filename
    if not destination.exists():
        store.save_upload(destination.parent, filename, (REPO / 'promptdb_colab/examples' / filename).read_bytes())
for example in (REPO / 'promptdb_colab/examples/workflows').glob('*.json'):
    destination = PRIVATE / 'workflows' / example.name
    if not destination.exists():
        destination.write_bytes(example.read_bytes())
print('Persistent workflow files:', [p.name for p in (PRIVATE / 'workflows').glob('*.json')])
if store_models_on_drive:
    setup.configure_model_cache(COMFY, PRIVATE / 'models')
run(sys.executable, '-m', 'pip', 'install', '-r', COMFY / 'requirements.txt')
''')
cell('code', '''# @title 2. 自動載入 Drive 提示庫、工作流與模型
setup.install(COMFY, preserve_existing=True)
def load_database(database, candidates, example):
    paths = [PRIVATE / 'user-db' / filename for filename in candidates]
    selected = next((path for path in paths if path.is_file()), None)
    if selected is None:
        selected = paths[0]
        store.save_upload(selected.parent, selected.name, (REPO / 'promptdb_colab/examples' / example).read_bytes())
    store.activate(COMFY, selected, database)
    print(database, 'Drive database:', selected)
load_database('krea2', ['prompt_defalut.json', 'prompts_krea2.json'], 'prompts_krea2.json')
load_database('illustrious', ['illustrious/prompts.json', 'prompts.json'], 'prompts.json')
setup.configure_web_navigation(COMFY)
setup.import_workflows(COMFY, PRIVATE / 'workflows')
if download_krea2_models:
    setup.download_models(COMFY, REPO / 'promptdb_colab/models.krea2.json')
print('Model directory:', (COMFY / 'models').resolve())
for model in sorted((PRIVATE / 'models').rglob('*.safetensors')):
    print('Available Drive model:', model.relative_to(PRIVATE), model.stat().st_size, 'bytes')
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
url = resume.main(verify_sample=False)
import html
display(HTML('<a target="_blank" href="' + html.escape(url, quote=True) + '">開啟 ComfyUI</a>'))
print('首次請選工作流程 → PromptDB-Drive → Krea2_PromptDB_Quick_Test，再按執行。')
''')
notebook = {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'accelerator': 'GPU', 'colab': {'gpuType': 'T4', 'provenance': []}, 'kernelspec': {'name': 'python3', 'display_name': 'Python 3'}, 'language_info': {'name': 'python'}}, 'cells': cells}
(ROOT / 'ComfyUI_PromptDB.ipynb').write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
