"""Install generic PromptDB and validate explicitly selected private data."""
import argparse
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


def install(comfy, data=None):
    comfy = Path(comfy)
    if not (comfy / "main.py").is_file():
        raise ValueError("Not a ComfyUI installation")
    source = Path(__file__).parent / "node"
    shutil.copytree(source, comfy / "custom_nodes" / "colab_promptdb", dirs_exist_ok=True)
    target = comfy / "user" / "default" / "user-db"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("prompts.json", "prompts_krea2.json"):
        src = Path(data) / name if data else Path(__file__).parent / "examples" / name
        if not src.is_file():
            continue
        validate_db(src)
        dst = target / name
        if dst.exists() and dst.read_bytes() != src.read_bytes():
            raise FileExistsError(f"Refusing to overwrite existing database: {dst}")
        shutil.copyfile(src, dst)


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
