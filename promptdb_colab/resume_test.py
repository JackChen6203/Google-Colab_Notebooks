"""Resume an installed Colab runtime and verify it without reinstalling models."""
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def main(verify_sample=True, output_directory=None):
    comfy = Path('/content/ComfyUI')
    root = Path(__file__).parent
    spec = importlib.util.spec_from_file_location('resume_promptdb_setup', root / 'setup.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.install(comfy, preserve_existing=True)
    changed = helper.configure_web_navigation(comfy)
    output_args = []
    if output_directory is not None:
        destination = Path(output_directory).resolve()
        destination.mkdir(parents=True, exist_ok=True)
        # Preserve previously generated images before switching output directories.
        original = comfy / 'output'
        if original.exists() and original.resolve() != destination:
            import hashlib
            for source in original.rglob('*'):
                if not source.is_file() or source.name.startswith('put_'):
                    continue
                target = destination / source.relative_to(original)
                if target.exists():
                    digest = hashlib.sha256(source.read_bytes()).hexdigest()
                    if hashlib.sha256(target.read_bytes()).hexdigest() == digest:
                        continue
                    target = target.with_name(target.stem + '-runtime-' + digest[:12] + target.suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        output_args = ['--output-directory', str(destination)]
        marker = Path('/content/comfyui-output-directory.txt')
        if not marker.exists() or marker.read_text() != str(destination):
            changed = True
        print('ComfyUI SaveImage output:', destination, flush=True)
    if changed:
        # Restart only this runtime's known ComfyUI command; retain models and other services.
        for process_dir in Path('/proc').iterdir():
            if not process_dir.name.isdigit():
                continue
            try:
                args = (process_dir / 'cmdline').read_bytes().decode().split('\0')
                if len(args) < 2:
                    continue
                cwd = (process_dir / 'cwd').resolve()
                script = (cwd / args[1]).resolve()
                if script != comfy / 'main.py':
                    continue
                if '--port' in args and args[args.index('--port') + 1] != '8188':
                    continue
                os.kill(int(process_dir.name), signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError, PermissionError, UnicodeDecodeError):
                continue
        time.sleep(2)
        print('Installed landing-page navigation compatibility and stopped the previous ComfyUI server.', flush=True)
    endpoint = 'http://127.0.0.1:8188'
    try:
        urllib.request.urlopen(endpoint + '/object_info', timeout=3).close()
    except OSError:
        output = open('/content/comfyui-resume.log', 'a')
        process = subprocess.Popen([sys.executable, str(comfy / 'main.py'), '--cache-none', '--port', '8188', *output_args],
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
    if output_directory is not None:
        Path('/content/comfyui-output-directory.txt').write_text(str(destination))
    if verify_sample:
        subprocess.run([sys.executable, str(root / 'verify_runtime.py')], check=True)
    executable = shutil.which('cloudflared')
    if not executable:
        raise FileNotFoundError('Run the original notebook with use_cloudflare enabled first')
    log_path = Path('/content/cloudflare-resume.log')
    output = log_path.open('w')
    tunnel = subprocess.Popen([executable, 'tunnel', '--protocol', 'http2', '--url', endpoint], stdout=output,
                              stderr=subprocess.STDOUT, start_new_session=True)
    last_error = 'Waiting for tunnel registration'
    for attempt in range(120):
        text = log_path.read_text()
        found = re.search(r'https://[a-z]+(?:-[a-z]+)+\.trycloudflare\.com', text)
        if found and 'Registered tunnel connection' in text and attempt % 3 == 0:
            url = found.group(0)
            try:
                with urllib.request.urlopen(url + '/object_info/PromptDB', timeout=8) as response:
                    info = json.load(response)
                if 'PromptDB' not in info:
                    raise ValueError('Public URL did not return this ComfyUI server')
                headers = {'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document'}
                with urllib.request.urlopen(urllib.request.Request(url + '/', headers=headers), timeout=8) as response:
                    page = response.read().decode('utf-8')
                if 'assets/' not in page:
                    raise ValueError('Public landing page is not the ComfyUI frontend')
                Path('/content/comfyui-public-url.txt').write_text(url, encoding='utf-8')
                print('COMFYUI_URL:', url, flush=True)
                print('Verified public ComfyUI page and PromptDB API. Generation is not part of this connection check.', flush=True)
                return url
            except (OSError, ValueError) as error:
                last_error = str(error)
                print('Tunnel registered, waiting for public DNS/HTTP:', last_error, flush=True)
        if tunnel.poll() is not None:
            raise RuntimeError(text[-4000:])
        time.sleep(1)
    raise TimeoutError('Public tunnel is not reachable: ' + last_error + '\n' + log_path.read_text()[-4000:])


if __name__ == '__main__':
    main()
