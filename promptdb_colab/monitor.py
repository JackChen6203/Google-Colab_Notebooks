"""Observe the ComfyUI queue without overriding Colab runtime limits."""
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def watch(drive_folder, interval=30):
    log = Path(drive_folder) / 'logs/session-monitor.jsonl'
    log.parent.mkdir(parents=True, exist_ok=True)
    previous = None
    print('正在監控 ComfyUI 佇列；此功能不能阻止 Colab 回收 runtime。停止此格只結束監控。', flush=True)
    try:
        while True:
            try:
                with urllib.request.urlopen('http://127.0.0.1:8188/queue', timeout=10) as response:
                    queue = json.load(response)
                state = {'running': len(queue['queue_running']), 'pending': len(queue['queue_pending'])}
            except (OSError, ValueError, KeyError, TypeError) as error:
                state = {'error': str(error)}
            if state != previous:
                event = {'time': datetime.now(timezone.utc).isoformat(), **state}
                print(event, flush=True)
                try:
                    with log.open('a', encoding='utf-8') as stream:
                        stream.write(json.dumps(event, ensure_ascii=False) + '\n')
                    if 'error' in state:
                        for name in ('comfyui-resume.log', 'cloudflare-resume.log'):
                            source = Path('/content') / name
                            if source.exists():
                                with source.open('rb') as stream:
                                    stream.seek(max(0, source.stat().st_size - 16000))
                                    (log.parent / name).write_bytes(stream.read())
                except OSError as error:
                    print('無法寫入 Drive 診斷紀錄：', error, flush=True)
                previous = state
            time.sleep(interval)
    except KeyboardInterrupt:
        print('監控已停止；ComfyUI 與 Tunnel 背景程序未被此監控停止。', flush=True)
