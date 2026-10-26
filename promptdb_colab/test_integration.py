"""Check that every upstream program survives the additive integration."""
import importlib.util
import json
import re
import subprocess
import unittest
import copy
import ast
import types
from unittest.mock import Mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = '774889ce437cae9e397ba8bfaab6040cffd39a79'
spec = importlib.util.spec_from_file_location('integrator', Path(__file__).with_name('integrate_notebooks.py'))
integrator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(integrator)


class IntegrationTests(unittest.TestCase):
    def test_invalid_database_does_not_abort_notebook_startup(self):
        notebook = json.loads((ROOT / 'ComfyUI_PromptDB.ipynb').read_text(encoding='utf-8'))
        source = next(''.join(c['source']) for c in notebook['cells'] if 'def load_database(' in ''.join(c['source']))
        tree = ast.parse(source)
        loader = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'load_database')
        selected = Mock()
        selected.stat.return_value.st_size = 123
        store = types.SimpleNamespace(select_existing=Mock(side_effect=[selected, ValueError('invalid nested value')]), activate=Mock())
        scope = {'store': store, 'PRIVATE': Path('/drive'), 'COMFY': Path('/comfy'), 'print': Mock()}
        exec(compile(ast.Module(body=[loader], type_ignores=[]), '<notebook loader>', 'exec'), scope)
        scope['load_database']('krea2')
        scope['load_database']('illustrious')
        store.activate.assert_called_once_with(Path('/comfy'), selected, 'krea2')
        self.assertTrue(any('繼續啟動 ComfyUI' in str(call) for call in scope['print'].call_args_list))

    def test_all_upstream_notebooks_preserved(self):
        paths = list((ROOT / 'ComfyUI').rglob('*.ipynb'))
        self.assertEqual(len(paths), 17)
        for path in paths:
            with self.subTest(notebook=path.name):
                relative = path.relative_to(ROOT).as_posix()
                original = json.loads(subprocess.check_output(['git', 'show', f'{BASE}:{relative}'], cwd=ROOT))
                current = json.loads(path.read_text(encoding='utf-8'))
                config = [c for c in current['cells'] if c.get('id') == 'promptdb-options']
                self.assertEqual(len(config), 1)
                compile(''.join(config[0]['source']), str(path), 'exec')
                cells = [c for c in current['cells'] if c.get('id') != 'promptdb-options']
                self.assertEqual(len(cells), len(original['cells']))
                for before, after in zip(original['cells'], cells):
                    source = ''.join(after['source'])
                    restored = re.sub(r'# BEGIN COLAB PROMPTDB INTEGRATION\n.*?# END COLAB PROMPTDB INTEGRATION\n\n', '', source, flags=re.S)
                    self.assertEqual(restored.rstrip(), ''.join(before['source']).rstrip())
                code = '\n'.join(''.join(c['source']) for c in cells if c['cell_type'] == 'code')
                self.assertIn('install_colab_promptdb()', code)
                if path.parent.name != 'Z_Image':
                    self.assertLess(code.index('install_colab_promptdb()'), code.index('use_cloudflare ='))
                self.assertIn('configure_colab_model_storage()', code)
                first_download = re.search(r'^def (?:download_\w+|model_download\w*|pull)\(', code, re.M)
                self.assertLess(code.index('configure_colab_model_storage()'), first_download.start())
                self.assertEqual(integrator.integrate(copy.deepcopy(current), direct=path.parent.name == 'Z_Image'), current)

    def test_root_entry_is_full_upstream_ui(self):
        root = json.loads((ROOT / 'ComfyUI_PromptDB.ipynb').read_text(encoding='utf-8'))
        full = json.loads((ROOT / 'ComfyUI/ComfyUI_Flux1Dev_USO/ComfyUI_Flux1Dev_USO.ipynb').read_text(encoding='utf-8'))
        code = '\n'.join(''.join(c['source']) for c in root['cells'])
        for feature in ('drive.mount', 'store.activate', 'resume.main', 'cloudflared', 'load_database'):
            self.assertIn(feature, code)
        self.assertNotIn('files.upload', code)
        self.assertNotIn('upload_prompt =', code)
        self.assertIn("output_directory=PRIVATE / 'output'", code)
        self.assertNotIn('store.save_upload', code)
        startup_cells = [c for c in root['cells'] if 'resume.main(' in ''.join(c['source'])]
        self.assertEqual(len(startup_cells), 1)
        self.assertIn('load_database', ''.join(startup_cells[0]['source']))
        for cell in root['cells']:
            if cell['cell_type'] == 'code':
                compile(''.join(cell['source']), '<single notebook>', 'exec')


if __name__ == '__main__':
    unittest.main()
