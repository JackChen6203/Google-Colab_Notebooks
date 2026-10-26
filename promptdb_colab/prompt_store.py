"""Validated persistent JSON uploads and runtime database links."""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

DATABASE_FILES = {'krea2': 'prompts_krea2.json', 'illustrious': 'prompts.json'}


def decode(data):
    value = json.loads(data.decode('utf-8-sig'))
    if not isinstance(value, dict) or not value or not all(
        isinstance(category, str) and isinstance(entries, dict)
        and all(isinstance(name, str) and isinstance(text, str) for name, text in entries.items())
        for category, entries in value.items()
    ):
        raise ValueError('Expected JSON category -> prompt name -> prompt text')
    return value


def timestamp():
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')


def save_upload(folder, filename, data):
    if Path(filename).name != filename or '/' in filename or '\\' in filename or not filename.lower().endswith('.json'):
        raise ValueError('Prompt filename must be a single JSON filename')
    decode(data)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    if target.exists() and target.read_bytes() != data:
        backup = folder / 'prompt-backups' / (timestamp() + '-' + filename)
        backup.parent.mkdir(exist_ok=True)
        shutil.copyfile(target, backup)
    temporary = target.with_name(target.name + '.uploading')
    temporary.write_bytes(data)
    temporary.replace(target)
    return target


def activate(comfy, source, database='krea2'):
    source = Path(source).resolve()
    decode(source.read_bytes())
    if database not in DATABASE_FILES:
        raise ValueError('Unknown database')
    comfy = Path(comfy).resolve()
    if not (comfy / 'main.py').is_file():
        raise ValueError('Not a ComfyUI installation')
    folder = comfy / 'user/default/user-db'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / DATABASE_FILES[database]
    if target.is_symlink() and target.resolve() == source:
        return target
    # Create the replacement first; a failure preserves the current runtime DB.
    pending = folder / (target.name + '.' + timestamp() + '.link')
    pending.symlink_to(source)
    try:
        if target.exists() or target.is_symlink():
            backups = folder / 'prompt-backups'
            backups.mkdir(exist_ok=True)
            target.rename(backups / (timestamp() + '-' + target.name))
        pending.replace(target)
    finally:
        pending.unlink(missing_ok=True)
    return target
