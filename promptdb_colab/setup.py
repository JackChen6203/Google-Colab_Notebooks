"""Install generic PromptDB and validate explicitly selected private data."""
import argparse
import importlib.util
import hashlib
import json
import shutil
import urllib.request
from pathlib import Path


def inside(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    if path == root or root not in path.parents:
        raise ValueError(f"Path escapes destination: {relative}")
    return path


def validate_db(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not all(
        isinstance(category, str) and isinstance(entries, dict)
        and all(isinstance(k, str) and isinstance(v, str) for k, v in entries.items())
        for category, entries in data.items()
    ):
        raise ValueError(f"Expected category -> name -> text: {path}")
    return data


def configure_model_cache(comfy, cache):
    """Point a fresh runtime's model directory to persistent Drive storage."""
    comfy = Path(comfy).resolve()
    models = comfy / 'models'
    cache = Path(cache).resolve()
    if cache == comfy or comfy in cache.parents:
        raise ValueError('Persistent cache must be outside the runtime ComfyUI folder')
    if models.is_symlink():
        if models.resolve() != cache:
            raise ValueError('Models already point to a different cache')
        return
    inside(comfy, 'models')
    if not (comfy / 'main.py').is_file():
        raise ValueError('Configure cache after cloning ComfyUI')
    if models.exists():
        existing = [p for p in models.rglob('*') if p.is_file()
                    and not (p.name.startswith('put_') or p.name in {'.gitkeep', 'README.md', '.gitignore'})]
        cache.mkdir(parents=True, exist_ok=True)
        def checksum(path):
            value = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                    value.update(block)
            return value.digest()
        # Check every conflict before copying or changing runtime paths.
        for source in existing:
            destination = inside(cache, source.relative_to(models))
            if destination.exists() and (destination.stat().st_size != source.stat().st_size or checksum(destination) != checksum(source)):
                raise FileExistsError(f'Drive model differs; both files preserved: {destination}')
        for source in existing:
            destination = inside(cache, source.relative_to(models))
            if destination.exists():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            print(f'Copying existing runtime model to Drive: {source.relative_to(models)}', flush=True)
            pending = destination.with_name(destination.name + '.migrating')
            shutil.copyfile(source, pending)
            if checksum(pending) != checksum(source):
                raise IOError(f'Model copy verification failed; original preserved: {source}')
            pending.replace(destination)
    backup = comfy / 'models.runtime-original'
    if backup.exists():
        raise FileExistsError(f'Model directory backup already exists: {backup}')
    cache.mkdir(parents=True, exist_ok=True)
    if models.exists():
        # The resolved model directory was checked to stay inside this ComfyUI root.
        models.rename(backup)
    try:
        models.symlink_to(cache, target_is_directory=True)
    except OSError:
        if backup.exists():
            backup.rename(models)
        raise


def install(comfy, data=None, preserve_existing=False):
    comfy = Path(comfy)
    if not (comfy / "main.py").is_file():
        raise ValueError("Not a ComfyUI installation")
    source = Path(__file__).parent / "node"
    node_target = comfy / "custom_nodes" / "colab_promptdb"
    node_target.mkdir(parents=True, exist_ok=True)
    # Only ship reviewed runtime files, not incidental local edits or caches.
    for name in ("__init__.py", "prompt_db.py", "cast_compat.py", "text_join.py", "LICENSE"):
        shutil.copyfile(source / name, node_target / name)
    shutil.copytree(source / "web", node_target / "web", dirs_exist_ok=True)
    target = comfy / "user" / "default" / "user-db"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("prompts.json", "prompts_krea2.json"):
        src = Path(data) / name if data else Path(__file__).parent / "examples" / name
        if not src.is_file():
            continue
        validate_db(src)
        dst = target / name
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            if preserve_existing:
                validate_db(dst)
                continue
            raise FileExistsError(f"Refusing to overwrite existing database: {dst}")
        shutil.copyfile(src, dst)
    import_workflows(comfy, Path(__file__).parent / "examples/workflows")


def configure_web_navigation(comfy):
    spec = importlib.util.spec_from_file_location('promptdb_web_compat', Path(__file__).with_name('web_compat.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.apply(comfy)


def download_models(comfy, manifest):
    entries = json.loads(Path(manifest).read_text(encoding="utf-8"))
    for entry in entries:
        dst = inside(Path(comfy) / "models", entry["path"])
        url, expected = entry["url"], entry["sha256"]
        if not url.startswith("https://") or len(expected) != 64:
            raise ValueError("Each download requires HTTPS and a SHA256 digest")
        def digest(path):
            h = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    h.update(block)
            return h.hexdigest()
        if dst.exists():
            if digest(dst) != expected:
                raise ValueError(f"Existing model checksum mismatch: {dst}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        print(f'Downloading and verifying model: {entry["path"]}', flush=True)
        temporary = dst.with_name(dst.name + ".partial")
        try:
            with urllib.request.urlopen(url) as response, temporary.open("wb") as output:
                if not response.url.startswith("https://"):
                    raise ValueError("Download redirected away from HTTPS")
                shutil.copyfileobj(response, output)
            if digest(temporary) != expected:
                raise ValueError(f"Downloaded model checksum mismatch: {dst.name}")
            temporary.replace(dst)
        finally:
            temporary.unlink(missing_ok=True)


def import_workflows(comfy, source):
    """Copy selected UI workflows to the menu without changing their node data."""
    target = Path(comfy) / 'user/default/workflows/PromptDB-Drive'
    for path in sorted(Path(source).glob('*.json')):
        workflow = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(workflow, dict) or not isinstance(workflow.get('nodes'), list):
            raise ValueError(f'Expected a ComfyUI UI workflow: {path}')
        target.mkdir(parents=True, exist_ok=True)
        dst = target / path.name
        if dst.exists() and dst.read_bytes() != path.read_bytes():
            raise FileExistsError(f'Refusing to overwrite workflow: {dst}')
        shutil.copyfile(path, dst)


def audit(comfy, workflows, endpoint):
    with urllib.request.urlopen(endpoint.rstrip("/") + "/object_info") as response:
        registered = json.load(response)
    available = {p.name for p in (Path(comfy) / "models").rglob("*") if p.is_file()}
    reports = []
    for path in sorted(Path(workflows).glob("*.json")):
        workflow = json.loads(path.read_text(encoding="utf-8-sig"))
        nodes = workflow.get("nodes", [])
        if not isinstance(nodes, list):
            raise ValueError(f"Expected UI workflow nodes: {path}")
        models = set()
        for node in nodes:
            for value in node.get("widgets_values", []) or []:
                if isinstance(value, str) and value.lower().endswith((".safetensors", ".gguf", ".ckpt", ".pt", ".pth")):
                    models.add(value.replace("\\", "/").split("/")[-1])
        reports.append({"workflow": path.name,
                        "missing_nodes": sorted({n["type"] for n in nodes if n["type"] not in registered and n["type"] not in {"Note", "MarkdownNote", "Reroute", "PrimitiveNode"}}),
                        "missing_models": sorted(models - available)})
    return reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comfy", required=True)
    parser.add_argument("--data")
    parser.add_argument("--manifest")
    args = parser.parse_args()
    install(args.comfy, args.data)
    if args.manifest:
        download_models(args.comfy, args.manifest)
