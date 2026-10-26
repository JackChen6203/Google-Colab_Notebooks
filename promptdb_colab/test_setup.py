import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("setup_promptdb", Path(__file__).with_name("setup.py"))
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class SetupTests(unittest.TestCase):
    def test_install_and_preserve_private_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "main.py").touch()
            setup.install(root)
            setup.install(root)
            target = root / "user/default/user-db/prompts.json"
            target.write_text('{"private":{"saved":"value"}}', encoding="utf-8")
            with self.assertRaises(FileExistsError):
                setup.install(root)
            self.assertEqual(json.loads(target.read_text())["private"]["saved"], "value")

    def test_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                setup.inside(directory, "../escape")

    def test_invalid_database_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"category":{"name":42}}', encoding="utf-8")
            with self.assertRaises(ValueError):
                setup.validate_db(path)

    def test_workflow_import_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'private'
            source.mkdir()
            workflow = source / 'landscape.json'
            workflow.write_text('{"nodes": []}', encoding='utf-8')
            setup.import_workflows(root / 'comfy', source)
            target = root / 'comfy/user/default/workflows/PromptDB-Drive/landscape.json'
            self.assertEqual(target.read_bytes(), workflow.read_bytes())
            target.write_text('{"nodes": [{"id":1}]}', encoding='utf-8')
            with self.assertRaises(FileExistsError):
                setup.import_workflows(root / 'comfy', source)

    def test_model_cache_refuses_conflicting_drive_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            comfy = root / 'comfy'
            (comfy / 'models').mkdir(parents=True)
            (comfy / 'main.py').touch()
            model = comfy / 'models/existing.safetensors'
            model.write_bytes(b'preserve')
            cache = root / 'drive/models'
            cache.mkdir(parents=True)
            (cache / model.name).write_bytes(b'different')
            with self.assertRaises(FileExistsError):
                setup.configure_model_cache(comfy, root / 'drive/models')
            self.assertEqual(model.read_bytes(), b'preserve')

    def test_model_cache_link_and_reuse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            comfy = root / 'comfy'
            (comfy / 'models').mkdir(parents=True)
            (comfy / 'main.py').touch()
            cache = root / 'drive/models'
            try:
                setup.configure_model_cache(comfy, cache)
            except OSError as error:
                if getattr(error, 'winerror', None) == 1314:
                    self.skipTest('Windows symlink privilege unavailable')
                raise
            (cache / 'persisted.safetensors').write_bytes(b'cached')
            setup.configure_model_cache(comfy, cache)
            self.assertEqual((comfy / 'models/persisted.safetensors').read_bytes(), b'cached')

    def test_existing_runtime_models_copied_and_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            comfy = root / 'comfy'
            (comfy / 'models/checkpoints').mkdir(parents=True)
            (comfy / 'main.py').touch()
            original = comfy / 'models/checkpoints/example.safetensors'
            original.write_bytes(b'actual model bytes')
            cache = root / 'drive/models'
            try:
                setup.configure_model_cache(comfy, cache)
            except OSError as error:
                if getattr(error, 'winerror', None) != 1314:
                    raise
                self.assertEqual(original.read_bytes(), b'actual model bytes')
            else:
                self.assertEqual((comfy / 'models.runtime-original/checkpoints/example.safetensors').read_bytes(), b'actual model bytes')
            self.assertEqual((cache / 'checkpoints/example.safetensors').read_bytes(), b'actual model bytes')


if __name__ == "__main__":
    unittest.main()
