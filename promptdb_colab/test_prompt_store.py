import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('prompt_store', Path(__file__).with_name('prompt_store.py'))
store = importlib.util.module_from_spec(spec)
spec.loader.exec_module(store)


class StoreTests(unittest.TestCase):
    def test_real_databases_win_over_old_defaults_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for name in ('prompts_krea2.json', 'prompt_defalut.json', 'prompts.json'):
                (folder / name).write_text('{"style":{"name":"' + name + '"}}', encoding='utf-8')
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            self.assertEqual(store.select_existing(folder, 'krea2').name, 'prompts_krea2.json')
            self.assertEqual(store.select_existing(folder, 'illustrious').name, 'prompts.json')
            self.assertEqual(before, {p.name: p.read_bytes() for p in folder.iterdir()})

    def test_custom_json_and_empty_folder_never_seed_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            self.assertIsNone(store.select_existing(folder, 'krea2'))
            self.assertEqual(list(folder.iterdir()), [])
            (folder / 'my_prompts.json').write_text('{"style":{"name":"custom"}}', encoding='utf-8')
            self.assertEqual(store.select_existing(folder, 'krea2').name, 'my_prompts.json')

    def test_upload_roundtrip_backup_and_invalid_file(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            data = b'{"style":{"landscape":"A mountain lake"}}'
            saved = store.save_upload(folder, 'prompt_defalut.json', data)
            self.assertEqual(store.decode(saved.read_bytes())['style']['landscape'], 'A mountain lake')
            store.save_upload(folder, saved.name, b'{"style":{"portrait":"An adult traveler"}}')
            self.assertEqual(next((folder / 'prompt-backups').iterdir()).read_bytes(), data)
            with self.assertRaises(ValueError):
                store.save_upload(folder, '../escape.json', data)
            with self.assertRaises(ValueError):
                store.save_upload(folder, 'invalid.json', b'{"category":42}')


if __name__ == '__main__':
    unittest.main()
