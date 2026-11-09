"""Kaggle runtime bootstrap for the PromptDB ComfyUI notebook.

Credentials are read from Kaggle Secrets and never printed.  The rclone
configuration is written with owner-only permissions and the remote is
normalized to the single name used by the notebook: ``gdrive:``.
"""

from __future__ import annotations

import configparser
import html
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


RCLONE_INSTALL_URL = "https://rclone.org/install.sh"
CLOUDFLARED_DEB_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-linux-amd64.deb"
)
REMOTE_NAME = "gdrive"
COMFY_ENDPOINT = "http://127.0.0.1:8188"
BACKUP_FOLDERS = ("models", "workflows", "user-db", "output", "logs")


def _run(args, *, label, input_text=None, timeout=None):
    """Run a fixed command while keeping captured error text out of notebook logs."""
    try:
        result = subprocess.run(
            [str(value) for value in args],
            input=input_text,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"{label} could not complete ({type(error).__name__}).") from None
    if result.returncode:
        raise RuntimeError(f"{label} failed (exit code {result.returncode}); details suppressed.")
    return result


def _load_setup_module(repo):
    path = Path(repo) / "promptdb_colab" / "setup.py"
    spec = importlib.util.spec_from_file_location("promptdb_kaggle_setup", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("PromptDB setup module could not be loaded from the selected branch.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_rclone_config(config_text):
    """Validate an rclone config and normalize its sole Drive remote to gdrive."""
    if not isinstance(config_text, str) or not config_text.strip():
        raise ValueError("The configured Kaggle Secret is empty.")
    if len(config_text) > 1_000_000:
        raise ValueError("The rclone configuration is unexpectedly large.")

    config = configparser.ConfigParser(interpolation=None)
    try:
        config.read_string(config_text)
    except configparser.Error:
        raise ValueError("The rclone secret is not a valid rclone configuration.") from None

    drive_sections = [
        section
        for section in config.sections()
        if config.get(section, "type", fallback="").strip().lower() == "drive"
    ]
    if config.has_section(REMOTE_NAME):
        if config.get(REMOTE_NAME, "type", fallback="").strip().lower() != "drive":
            raise ValueError("The [gdrive] remote must use rclone type=drive.")
    elif len(drive_sections) == 1:
        selected = drive_sections[0]
        values = dict(config.items(selected))
        config.remove_section(selected)
        config.add_section(REMOTE_NAME)
        for key, value in values.items():
            config.set(REMOTE_NAME, key, value)
    else:
        raise ValueError(
            "The rclone secret must contain one Google Drive remote, or a [gdrive] remote."
        )

    scope = config.get(REMOTE_NAME, "scope", fallback="drive").strip().lower()
    if scope != "drive":
        raise ValueError(
            "Google Drive OAuth scope must be 'drive' for read/write synchronization."
        )
    if not config.has_option(REMOTE_NAME, "token"):
        raise ValueError("The [gdrive] remote is missing its OAuth token configuration.")
    if not config.get(REMOTE_NAME, "client_id", fallback="").strip():
        raise ValueError("The [gdrive] remote needs a custom Google OAuth client_id.")
    if not config.get(REMOTE_NAME, "client_secret", fallback="").strip():
        raise ValueError("The [gdrive] remote needs a custom Google OAuth client_secret.")

    token_text = config.get(REMOTE_NAME, "token", fallback="")
    try:
        token = json.loads(token_text)
    except (TypeError, ValueError):
        raise ValueError("The [gdrive] OAuth token is not valid JSON.") from None
    if not isinstance(token, dict) or not (
        token.get("access_token") or token.get("refresh_token")
    ):
        raise ValueError("The [gdrive] OAuth token is missing access or refresh data.")
    granted_scopes = token.get("scope", "")
    if isinstance(granted_scopes, str) and granted_scopes:
        if "https://www.googleapis.com/auth/drive" not in granted_scopes.split():
            raise ValueError("The [gdrive] OAuth token must grant full Google Drive read/write scope.")

    config.set(REMOTE_NAME, "scope", "drive")
    from io import StringIO

    output = StringIO()
    config.write(output)
    return output.getvalue()


def _read_kaggle_secret(secret_name):
    try:
        from kaggle_secrets import UserSecretsClient

        value = UserSecretsClient().get_secret(secret_name)
    except Exception:
        raise RuntimeError(
            f"Kaggle Secret {secret_name!r} is unavailable. Add it under Add-ons > Secrets "
            "and attach it to this notebook. Secret values are never printed."
        ) from None
    if not isinstance(value, str) or not value.strip():
        raise RuntimeError(f"Kaggle Secret {secret_name!r} is empty or unavailable.")
    return value


def _install_rclone():
    if shutil.which("rclone"):
        return
    try:
        with urllib.request.urlopen(RCLONE_INSTALL_URL, timeout=30) as response:
            script = response.read()
    except (OSError, urllib.error.URLError):
        raise RuntimeError("Could not download the rclone installer from rclone.org.") from None
    _run(["bash", "-s"], label="rclone installation", input_text=script.decode("utf-8"), timeout=300)
    if not shutil.which("rclone"):
        raise RuntimeError("rclone installation finished without an rclone executable.")
    print("Installed rclone from the official rclone.org installer.", flush=True)


def _install_cloudflared():
    if shutil.which("cloudflared"):
        return
    deb = Path("/kaggle/temp/promptdb-runtime/cloudflared-linux-amd64.deb")
    deb.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(CLOUDFLARED_DEB_URL, timeout=60) as response:
            with deb.open("wb") as output:
                shutil.copyfileobj(response, output)
    except (OSError, urllib.error.URLError):
        raise RuntimeError("Could not download cloudflared from the official Cloudflare release.") from None
    _run(["apt-get", "update", "-qq"], label="Cloudflare package index update", timeout=300)
    _run(["apt-get", "install", "-y", str(deb)], label="cloudflared installation", timeout=300)
    if not shutil.which("cloudflared"):
        raise RuntimeError("cloudflared installation finished without a cloudflared executable.")
    print("Installed cloudflared from the official Cloudflare release.", flush=True)


def _remote_path(drive_folder, subfolder):
    folder = str(drive_folder).strip().strip("/")
    if not folder or ":" in folder or any(part == ".." for part in folder.split("/")):
        raise ValueError("drive_folder must be a relative Google Drive folder path.")
    return f"{REMOTE_NAME}:{folder}/{subfolder}" if subfolder else f"{REMOTE_NAME}:{folder}"


def _rclone(config_path, *args, label):
    return _run(
        ["rclone", "--config", config_path, *args, "--log-level", "ERROR"],
        label=label,
        timeout=3600,
    )


def _copy_remote_to_local(config_path, remote, local):
    Path(local).mkdir(parents=True, exist_ok=True)
    _rclone(
        config_path,
        "copy",
        remote,
        local,
        "--transfers",
        "4",
        "--checkers",
        "8",
        "--create-empty-src-dirs",
        label="Google Drive download",
    )


def _copy_local_to_remote(config_path, local, remote, *, min_age=None):
    Path(local).mkdir(parents=True, exist_ok=True)
    args = [
        "copy",
        local,
        remote,
        "--transfers",
        "4",
        "--checkers",
        "8",
        "--create-empty-src-dirs",
        "--exclude",
        "*.partial",
        "--exclude",
        "*.tmp",
        "--exclude",
        "*.uploading",
        "--exclude",
        "*.migrating",
    ]
    if min_age:
        args.extend(["--min-age", min_age])
    _rclone(config_path, *args, label="Google Drive backup")


def _backup_all(context, *, final=False):
    for folder in BACKUP_FOLDERS:
        if folder == "models" and not context.get("store_models_on_drive", True):
            continue
        local = context["private"] / folder
        remote = _remote_path(context["drive_folder"], folder)
        # Avoid copying a still-growing image during periodic backups. Final backup
        # includes recent files when the user stops the monitoring cell normally.
        age = None if final or folder != "output" else "60s"
        try:
            _copy_local_to_remote(context["rclone_config"], local, remote, min_age=age)
        except RuntimeError as error:
            print(f"Drive backup for {folder} failed: {error}", flush=True)
            return False
    print("Google Drive backup completed (models, workflows, prompt databases, output, logs).", flush=True)
    return True


def _backup_loop(context, stop_event, interval):
    while not stop_event.wait(interval):
        _backup_all(context)


def bootstrap(
    repo,
    *,
    drive_folder="ComfyUI-PromptDB",
    rclone_secret_name="RCLONE_CONFIG_TEXT",
    store_models_on_drive=True,
    download_krea2_models=True,
    force_verify_models=False,
):
    """Prepare Drive data, ComfyUI, PromptDB and default Krea2 models."""
    repo = Path(repo).resolve()
    # Keep large models and the ComfyUI checkout outside /kaggle/working so Kaggle
    # does not try to package them as notebook output files at the end of a run.
    working = Path("/kaggle/temp/promptdb-runtime")
    working.mkdir(parents=True, exist_ok=True)
    private = working / "ComfyUI-PromptDB"
    comfy = working / "ComfyUI"
    logs = private / "logs"
    for folder in ("output", "models", "workflows", "user-db", "logs"):
        (private / folder).mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    _install_rclone()
    config_text = _read_kaggle_secret(rclone_secret_name)
    normalized = normalize_rclone_config(config_text)
    rclone_config = working / ".config" / "rclone" / "rclone.conf"
    rclone_config.parent.mkdir(parents=True, exist_ok=True)
    rclone_config.write_text(normalized, encoding="utf-8")
    rclone_config.chmod(0o600)
    del config_text, normalized

    remotes = _rclone(rclone_config, "listremotes", label="rclone remote validation").stdout.splitlines()
    if f"{REMOTE_NAME}:" not in remotes:
        raise RuntimeError("The configured Google Drive remote did not resolve to gdrive:.")
    _rclone(rclone_config, "about", "gdrive:", label="Google Drive OAuth authorization")
    print("Google Drive OAuth authorization verified for the gdrive: remote.", flush=True)

    base = _remote_path(drive_folder, "")
    for folder in BACKUP_FOLDERS:
        _rclone(
            rclone_config,
            "mkdir",
            _remote_path(drive_folder, folder),
            label="Google Drive folder preparation",
        )
    sync_folders = ["workflows", "user-db", "logs"]
    if store_models_on_drive:
        sync_folders.insert(0, "models")
    for folder in sync_folders:
        _copy_remote_to_local(
            rclone_config,
            _remote_path(drive_folder, folder),
            private / folder,
        )
    print(f"Google Drive workspace is ready: {base}", flush=True)

    if not (comfy / "main.py").is_file():
        _run(["git", "clone", "https://github.com/Comfy-Org/ComfyUI.git", comfy], label="ComfyUI clone", timeout=900)
    else:
        print("Using the existing Kaggle ComfyUI checkout.", flush=True)

    setup = _load_setup_module(repo)
    if store_models_on_drive:
        setup.configure_model_cache(comfy, private / "models")

    requirements = comfy / "requirements.txt"
    _run(
        [sys.executable, "-m", "pip", "install", "-r", requirements],
        label="ComfyUI dependency installation",
        timeout=1800,
    )
    print("ComfyUI dependencies are ready.", flush=True)

    examples = repo / "promptdb_colab" / "examples" / "workflows"
    for source in examples.glob("*.json"):
        destination = private / "workflows" / source.name
        if not destination.exists():
            shutil.copyfile(source, destination)

    setup.install(comfy, preserve_existing=True, seed_examples=False)
    setup.configure_web_navigation(comfy)
    workflow_target = comfy / "user" / "default" / "workflows" / "PromptDB-Drive"
    workflow_target.parent.mkdir(parents=True, exist_ok=True)
    if workflow_target.is_symlink():
        if workflow_target.resolve() != (private / "workflows").resolve():
            raise RuntimeError("The PromptDB workflow directory points to an unexpected location.")
    elif workflow_target.exists():
        for existing in workflow_target.iterdir():
            destination = private / "workflows" / existing.name
            if destination.exists() and existing.is_file() and destination.read_bytes() != existing.read_bytes():
                raise RuntimeError(f"Conflicting Drive workflow preserved: {existing.name}")
            if existing.is_file() and not destination.exists():
                shutil.copyfile(existing, destination)
        shutil.rmtree(workflow_target)
        workflow_target.symlink_to(private / "workflows", target_is_directory=True)
    else:
        workflow_target.symlink_to(private / "workflows", target_is_directory=True)

    # Databases already stored on Drive remain the source of truth; absent files are
    # not replaced with examples, and malformed files are preserved for diagnosis.
    spec = importlib.util.spec_from_file_location(
        "promptdb_kaggle_store", repo / "promptdb_colab" / "prompt_store.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("PromptDB database loader could not be loaded.")
    prompt_store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prompt_store)
    for database in ("krea2", "illustrious", "krea2-口交", "krea2-影片"):
        try:
            selected = prompt_store.select_existing(private / "user-db", database)
            if selected is not None:
                prompt_store.activate(comfy, selected, database)
                print(f"Activated Drive prompt database: {database}.", flush=True)
            else:
                print(f"No Drive prompt JSON found for {database}; no file was created.", flush=True)
        except (OSError, ValueError, UnicodeError) as error:
            print(
                f"Prompt database {database} was not activated ({type(error).__name__}); "
                "the original Drive file was preserved.",
                flush=True,
            )

    if download_krea2_models:
        manifest = repo / "promptdb_colab" / "models.krea2.json"
        setup.download_models(comfy, manifest, force_verify=force_verify_models)
    print("PromptDB bootstrap completed.", flush=True)

    return {
        "repo": repo,
        "comfy": comfy,
        "private": private,
        "logs": logs,
        "rclone_config": rclone_config,
        "drive_folder": drive_folder,
        "store_models_on_drive": store_models_on_drive,
    }


def _wait_for_local_server(process, log_path, timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"ComfyUI exited with code {process.returncode}; inspect Drive logs/comfyui.log."
            )
        try:
            with urllib.request.urlopen(COMFY_ENDPOINT + "/object_info", timeout=3):
                return
        except (OSError, urllib.error.URLError):
            time.sleep(2)
    raise TimeoutError(f"ComfyUI did not become ready; inspect Drive logs/{log_path.name}.")


def _verify_public_tunnel(url):
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url + "/object_info/PromptDB", timeout=8) as response:
                info = json.load(response)
            if "PromptDB" not in info:
                raise ValueError("PromptDB API route was not present.")
            headers = {
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Dest": "document",
            }
            request = urllib.request.Request(url + "/", headers=headers)
            with urllib.request.urlopen(request, timeout=8) as response:
                page = response.read().decode("utf-8", errors="replace")
            if "assets/" not in page:
                raise ValueError("ComfyUI frontend did not load through the tunnel.")
            return
        except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
            time.sleep(5)
    raise TimeoutError("The Cloudflare URL did not return the ComfyUI UI and PromptDB API.")


def start_services(context, *, enable_cloudflare=True, backup_output=True, backup_interval=120):
    """Start ComfyUI and an optional temporary Cloudflare quick tunnel."""
    comfy = context["comfy"]
    private = context["private"]
    logs = context["logs"]
    output = private / "output"
    output.mkdir(parents=True, exist_ok=True)
    comfy_log = logs / "comfyui.log"
    server_log = comfy_log.open("a", encoding="utf-8")
    server = subprocess.Popen(
        [
            sys.executable,
            str(comfy / "main.py"),
            "--listen",
            "0.0.0.0",
            "--port",
            "8188",
            "--cache-none",
            "--output-directory",
            str(output),
        ],
        cwd=comfy,
        stdout=server_log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    _wait_for_local_server(server, comfy_log)
    print("ComfyUI is ready on Kaggle port 8188.", flush=True)

    tunnel = None
    if enable_cloudflare:
        _install_cloudflared()
        tunnel_log = logs / "cloudflared.log"
        tunnel_output = tunnel_log.open("a", encoding="utf-8")
        tunnel = subprocess.Popen(
            [shutil.which("cloudflared"), "tunnel", "--no-autoupdate", "--url", COMFY_ENDPOINT],
            stdout=tunnel_output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        url = None
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            if tunnel.poll() is not None:
                raise RuntimeError(
                    f"cloudflared exited with code {tunnel.returncode}; inspect Drive logs/cloudflared.log."
                )
            text = tunnel_log.read_text(encoding="utf-8", errors="replace")
            match = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", text)
            if match:
                url = match.group(0)
                break
            time.sleep(2)
        if not url:
            raise TimeoutError("Cloudflare did not provide a quick-tunnel URL within 180 seconds.")
        _verify_public_tunnel(url)
        (private / "comfyui-public-url.txt").write_text(url + "\n", encoding="utf-8")
        print("COMFYUI_URL:", url, flush=True)
        print("Verified the public ComfyUI page and PromptDB API; no image was generated.", flush=True)
        try:
            from IPython.display import HTML, display

            display(HTML(f'<a target="_blank" href="{html.escape(url, quote=True)}">Open ComfyUI (Cloudflare Tunnel)</a>'))
        except ImportError:
            pass

    context["server"] = server
    context["tunnel"] = tunnel
    context["backup_stop"] = None
    context["backup_thread"] = None
    if backup_output:
        stop_event = threading.Event()
        worker = threading.Thread(
            target=_backup_loop,
            args=(context, stop_event, max(30, int(backup_interval))),
            daemon=True,
            name="promptdb-drive-backup",
        )
        worker.start()
        context["backup_stop"] = stop_event
        context["backup_thread"] = worker
        print(
            f"Output and PromptDB data will back up to Google Drive every {max(30, int(backup_interval))} seconds.",
            flush=True,
        )
    return url if enable_cloudflare else None


def monitor(context, interval=30):
    """Keep the notebook run active and record queue changes to Drive logs."""
    log_path = context["logs"] / "session-monitor.jsonl"
    previous = None
    print(
        "Monitoring ComfyUI. Keep this Kaggle cell running while you use the public URL.",
        flush=True,
    )
    try:
        while True:
            try:
                with urllib.request.urlopen(COMFY_ENDPOINT + "/queue", timeout=10) as response:
                    queue = json.load(response)
                state = {
                    "running": len(queue.get("queue_running", [])),
                    "pending": len(queue.get("queue_pending", [])),
                }
            except (OSError, urllib.error.URLError, ValueError, TypeError) as error:
                state = {"error_type": type(error).__name__}
            if state != previous:
                event = {"time": datetime.now(timezone.utc).isoformat(), **state}
                print(json.dumps(event, ensure_ascii=False), flush=True)
                with log_path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                previous = state
            time.sleep(max(5, int(interval)))
    except KeyboardInterrupt:
        print("Stopping PromptDB services and starting a final Drive backup.", flush=True)
        stop_event = context.get("backup_stop")
        if stop_event:
            stop_event.set()
        _backup_all(context, final=True)
        for name in ("tunnel", "server"):
            process = context.get(name)
            if process and process.poll() is None:
                process.terminate()
        print("Notebook monitoring stopped.", flush=True)
