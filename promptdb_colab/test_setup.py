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


if __name__ == "__main__":
    unittest.main()
