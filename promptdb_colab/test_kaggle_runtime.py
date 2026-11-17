import unittest

from kaggle_runtime import normalize_rclone_config


def config(remote, *, scope="drive"):
    return f"""[{remote}]
type = drive
client_id = example.apps.googleusercontent.com
client_secret = example-client-secret
scope = {scope}
token = {{"access_token":"example-access","refresh_token":"example-refresh","token_type":"Bearer"}}
"""


class NormalizeRcloneConfigTest(unittest.TestCase):
    def test_accepts_one_line_config(self):
        text = '[gdrive] type = drive scope = drive token = {"access_token":"private-value"}'
        self.assertIn('token = {"access_token":"private-value"}', normalize_rclone_config(text))

    def test_accepts_default_rclone_oauth_client(self):
        text = config("gdrive").replace("client_id = example.apps.googleusercontent.com\n", "")
        text = text.replace("client_secret = example-client-secret\n", "")
        self.assertIn("[gdrive]", normalize_rclone_config(text))

    def test_allows_section_header_comments(self):
        text = config("gdrive").replace("[gdrive]", "[gdrive] # comment")
        self.assertIn("[gdrive]", normalize_rclone_config(text))

    def test_keeps_existing_gdrive_remote(self):
        normalized = normalize_rclone_config(config("gdrive"))
        self.assertIn("[gdrive]", normalized)
        self.assertIn("scope = drive", normalized)
        self.assertIn('"refresh_token":"example-refresh"', normalized)

    def test_infers_missing_type_for_complete_drive_credentials(self):
        normalized = normalize_rclone_config(config("gdrive").replace("type = drive\n", ""))
        self.assertIn("type = drive", normalized)

    def test_rejects_explicit_non_drive_type(self):
        text = config("gdrive").replace("type = drive", "type = s3")
        with self.assertRaisesRegex(ValueError, r"type=drive"):
            normalize_rclone_config(text)

    def test_rejects_missing_type_and_incomplete_credentials(self):
        text = config("gdrive").replace("type = drive\n", "").replace("client_id = example.apps.googleusercontent.com\n", "")
        with self.assertRaisesRegex(ValueError, r"type=drive"):
            normalize_rclone_config(text)

    def test_renames_one_google_drive_remote_to_gdrive(self):
        normalized = normalize_rclone_config(config("GoogleDrive"))
        self.assertIn("[gdrive]", normalized)
        self.assertNotIn("[GoogleDrive]", normalized)

    def test_rejects_multiple_unselected_drive_remotes(self):
        text = config("primary") + "\n" + config("backup")
        with self.assertRaisesRegex(ValueError, r"one Google Drive remote"):
            normalize_rclone_config(text)

    def test_rejects_read_only_scope(self):
        with self.assertRaisesRegex(ValueError, r"scope must be 'drive'"):
            normalize_rclone_config(config("gdrive", scope="drive.readonly"))

    def test_requires_custom_oauth_client(self):
        text = config("gdrive").replace("client_secret = example-client-secret\n", "")
        with self.assertRaisesRegex(ValueError, r"custom Google OAuth client_secret"):
            normalize_rclone_config(text)

    def test_rejects_invalid_token_without_echoing_it(self):
        text = (
            "[gdrive]\ntype = drive\nclient_id = example.apps.googleusercontent.com\n"
            "client_secret = example-client-secret\nscope = drive\ntoken = never-log-this\n"
        )
        with self.assertRaisesRegex(ValueError, r"not valid JSON") as error:
            normalize_rclone_config(text)
        self.assertNotIn("never-log-this", str(error.exception))

class AcceleratorRuntimeTest(unittest.TestCase):
    def test_requires_selected_t4(self):
        from unittest.mock import patch
        import kaggle_runtime as runtime
        with patch.object(runtime.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "GPU T4"):
                runtime._validate_accelerator("gpu")

    def test_rejects_unknown_accelerator(self):
        import kaggle_runtime as runtime
        with self.assertRaisesRegex(ValueError, "accelerator"):
            runtime._validate_accelerator("cpu")

    def test_tpu_requirements_protect_torch_packages(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import kaggle_runtime as runtime
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            comfy = root / "comfy"
            comfy.mkdir()
            (comfy / "requirements.txt").write_text("torch\ntorchvision>=1\ntorch_xla==3\nlibtpu\nxformers\nnumpy>=1\n")
            with patch.object(runtime, "_run") as run:
                runtime._install_comfy_requirements(Path('/venv/bin/python'), comfy, root, "tpu")
            self.assertEqual((root / "tpu-requirements-no-accelerator.txt").read_text(), "numpy>=1\n")
            args = run.call_args.args[0]
            self.assertIn("--constraint", args)
            self.assertEqual(args[0], Path('/venv/bin/python'))

    def test_xla_patch_matches_pinned_hash(self):
        import hashlib
        from pathlib import Path
        import kaggle_runtime as runtime
        patch = Path(runtime.__file__).with_name("kaggle_comfyui_xla.patch")
        self.assertEqual(hashlib.sha256(patch.read_bytes()).hexdigest(), runtime.TPU_PATCH_SHA256)


if __name__ == "__main__":
    unittest.main()
