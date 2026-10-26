"""Allow opening ComfyUI's public landing page from a Colab link.

API requests, embeds and non-GET requests keep the upstream cross-site guard.
"""
from pathlib import Path

MARKER = '# PromptDB: allow top-level landing-page navigation only'
ORIGINAL = "            if sec_fetch_site == 'cross-site':\n                return web.Response(status=403)"
REPLACEMENT = """            # PromptDB: allow top-level landing-page navigation only
            landing_navigation = (
                request.method == 'GET'
                and request.path == '/'
                and request.headers.get('Sec-Fetch-Mode') == 'navigate'
                and request.headers.get('Sec-Fetch-Dest') == 'document'
            )
            if sec_fetch_site == 'cross-site' and not landing_navigation:
                return web.Response(status=403)"""


def patch_source(source):
    if MARKER in source:
        if REPLACEMENT not in source:
            raise ValueError('Existing navigation compatibility code differs; inspect server.py')
        return source
    if source.count(ORIGINAL) != 1:
        raise ValueError('Unsupported ComfyUI origin middleware; inspect server.py before applying compatibility patch')
    return source.replace(ORIGINAL, REPLACEMENT, 1)


def apply(comfy):
    path = Path(comfy) / 'server.py'
    if not path.exists():
        raise FileNotFoundError(f'ComfyUI server.py is missing: {path}')
    source = path.read_text(encoding='utf-8')
    updated = patch_source(source)
    if updated != source:
        backup = path.with_name('server.py.promptdb-before-navigation.bak')
        if not backup.exists():
            backup.write_bytes(path.read_bytes())
        path.write_text(updated, encoding='utf-8')
    return updated != source
