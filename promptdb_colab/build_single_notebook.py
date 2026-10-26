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
所有安裝、模型檢查、ComfyUI 啟動與 Cloudflare 連線檢查都在 Colab 虛擬機執行，無須在電腦執行程式。
同一 runtime 已掛載 Drive 時直接沿用；新 runtime 可能需要 Google 再次授權，Notebook 無法保證永久免授權。
模型首次完整 SHA256 驗證後，在同一 Drive 模型資料夾保存 .verified.json 紀錄；下次大小及修改時間相同即快速略過。勾選 force_verify_models 可強制重新完整驗證。
直接載入 Drive 已有 JSON；Krea2 優先 prompts_krea2.json，Illustrious 優先 prompts.json。不生成提示庫檔案。
提示庫、工作流與自行上傳的模型一律從 Drive 讀取，不會跳出選檔視窗。
Cloudflare 連結公開此 runtime 的 ComfyUI；停止 runtime 後網址失效。
''')
cell('code', '''# @title 1. 選項與環境安裝
store_models_on_drive = True # @param {type:"boolean"}
download_krea2_models = True # @param {type:"boolean"}
force_verify_models = False # @param {type:"boolean"}
drive_folder = "/content/drive/MyDrive/ComfyUI-PromptDB" # @param {type:"string"}
from pathlib import Path
import subprocess, sys, importlib.util, json
from google.colab import drive
import os
if os.path.ismount('/content/drive') and Path('/content/drive/MyDrive').is_dir():
    print('沿用目前 runtime 已掛載的 Google Drive。', flush=True)
else:
    print('正在掛載 Google Drive；新 runtime 可能需要您同意 Google 授權。', flush=True)
    drive.mount('/content/drive', force_remount=False)
PRIVATE = Path(drive_folder)
PRIVATE.mkdir(parents=True, exist_ok=True)
for relative in ('output', 'models/checkpoints', 'models/diffusion_models', 'models/text_encoders', 'models/vae', 'models/loras', 'workflows', 'user-db/illustrious'):
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
for example in (REPO / 'promptdb_colab/examples/workflows').glob('*.json'):
    destination = PRIVATE / 'workflows' / example.name
    if not destination.exists():
        destination.write_bytes(example.read_bytes())
print('Persistent workflow files:', [p.name for p in (PRIVATE / 'workflows').glob('*.json')])
if store_models_on_drive:
    setup.configure_model_cache(COMFY, PRIVATE / 'models')
run(sys.executable, '-m', 'pip', 'install', '-r', COMFY / 'requirements.txt')
''')
cell('markdown', '''## 2. 載入 Drive 並自動啟動 ComfyUI + Cloudflare Tunnel
執行下方儲存格會先載入提示庫、工作流及模型，接著安裝 cloudflared、啟動 ComfyUI 與公開 Tunnel。
等到出現 `COMFYUI_URL: https://….trycloudflare.com` 與「開啟 ComfyUI（Cloudflare Tunnel）」連結，即可直接進入。
如果仍在模型檢查／下載階段，Tunnel 尚未啟動；不需要點連結才啟動伺服器。
''')
cell('code', '''# @title 2. 載入 Drive + 啟動 ComfyUI 與 Cloudflare Tunnel
setup.install(COMFY, preserve_existing=True, seed_examples=False)
def load_database(database):
    try:
        selected = store.select_existing(PRIVATE / 'user-db', database)
    except (ValueError, UnicodeError, OSError) as error:
        print(database, '提示庫載入失敗：', error, flush=True)
        print('保留原始檔案，不建立預設檔；繼續啟動 ComfyUI。此提示庫本次未啟用。', flush=True)
        return
    if selected is None:
        print(database, 'No Drive JSON found; no file created.', flush=True)
        return
    try:
        store.activate(COMFY, selected, database)
    except (ValueError, UnicodeError, OSError) as error:
        print(database, '提示庫連結失敗：', selected, error, flush=True)
        print('此提示庫本次未更新；繼續啟動 ComfyUI。', flush=True)
        return
    print(database, 'Drive database:', selected, selected.stat().st_size, 'bytes', flush=True)
load_database('krea2')
load_database('illustrious')
setup.configure_web_navigation(COMFY)
print('Loading Drive workflows...', flush=True)
setup.import_workflows(COMFY, PRIVATE / 'workflows')
if download_krea2_models:
    print('Checking/downloading the three Krea2 model files...', flush=True)
    setup.download_models(COMFY, REPO / 'promptdb_colab/models.krea2.json', force_verify=force_verify_models)
print('Model directory:', (COMFY / 'models').resolve())
for model in sorted((PRIVATE / 'models').rglob('*.safetensors')):
    print('Available Drive model:', model.relative_to(PRIVATE), model.stat().st_size, 'bytes')
print('Workflow: PromptDB-Drive/Krea2_PromptDB_Quick_Test')
print('Starting ComfyUI server and Cloudflare automatically...', flush=True)
import shutil, urllib.request, runpy
from IPython.display import display, HTML
if not shutil.which('cloudflared'):
    package = Path('/content/cloudflared.deb')
    urllib.request.urlretrieve('https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb', package)
    run('dpkg', '-i', package)
resume = module('resume_test')
url = resume.main(verify_sample=False, output_directory=PRIVATE / 'output')
import html
display(HTML('<a target="_blank" href="' + html.escape(url, quote=True) + '">開啟 ComfyUI（Cloudflare Tunnel）</a>'))
print('首次請選工作流程 → PromptDB-Drive → Krea2_PromptDB_Quick_Test，再按執行。')
''')
notebook = {'nbformat': 4, 'nbformat_minor': 5, 'metadata': {'accelerator': 'GPU', 'colab': {'gpuType': 'T4', 'provenance': []}, 'kernelspec': {'name': 'python3', 'display_name': 'Python 3'}, 'language_info': {'name': 'python'}}, 'cells': cells}
(ROOT / 'ComfyUI_PromptDB.ipynb').write_text(json.dumps(notebook, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
