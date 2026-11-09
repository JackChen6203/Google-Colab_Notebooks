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
    def test_keeps_existing_gdrive_remote(self):
        normalized = normalize_rclone_config(config("gdrive"))
        self.assertIn("[gdrive]", normalized)
        self.assertIn("scope = drive", normalized)
        self.assertIn('"refresh_token":"example-refresh"', normalized)

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


if __name__ == "__main__":
    unittest.main()
