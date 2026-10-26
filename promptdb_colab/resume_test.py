"""Resume an installed Colab runtime and verify it without reinstalling models."""
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def main():
    comfy = Path('/content/ComfyUI')
    root = Path(__file__).parent
    spec = importlib.util.spec_from_file_location('resume_promptdb_setup', root / 'setup.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.install(comfy)
    endpoint = 'http://127.0.0.1:8188'
    try:
        urllib.request.urlopen(endpoint + '/object_info', timeout=3).close()
    except OSError:
        output = open('/content/comfyui-resume.log', 'a')
        process = subprocess.Popen([sys.executable, str(comfy / 'main.py'), '--cache-none', '--port', '8188'],
                                   cwd=comfy, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(90):
            if process.poll() is not None:
                raise RuntimeError(Path('/content/comfyui-resume.log').read_text()[-6000:])
            try:
                urllib.request.urlopen(endpoint + '/object_info', timeout=2).close()
                break
            except OSError:
                time.sleep(1)
        else:
            raise TimeoutError('Inspect /content/comfyui-resume.log')
    subprocess.run([sys.executable, str(root / 'verify_runtime.py')], check=True)
    executable = shutil.which('cloudflared')
    if not executable:
        raise FileNotFoundError('Run the original notebook with use_cloudflare enabled first')
    log_path = Path('/content/cloudflare-resume.log')
    output = log_path.open('w')
    tunnel = subprocess.Popen([executable, 'tunnel', '--url', endpoint], stdout=output,
                              stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(60):
        text = log_path.read_text()
        found = re.search(r'https://[a-z]+(?:-[a-z]+)+\.trycloudflare\.com', text)
        if found:
            print('COMFYUI_URL:', found.group(0), flush=True)
            print('Background service ready; generation has not been tested.', flush=True)
            return
        if tunnel.poll() is not None:
            raise RuntimeError(text[-4000:])
        time.sleep(1)
    raise TimeoutError('Inspect /content/cloudflare-resume.log')


if __name__ == '__main__':
    main()
