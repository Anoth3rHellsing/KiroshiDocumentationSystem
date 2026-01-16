
import sys
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import io
import secrets
import base64

# Add repo root to sys.path
sys.path.append(os.getcwd())

import kiroshi_cloud_sync

class TestSecureInitialization(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_path = Path(self.test_dir) / "cloud_config.json"

        self.patcher = patch("kiroshi_cloud_sync.CLOUD_CONFIG_PATH", self.config_path)
        self.patcher.start()

        self.ensure_dirs_patcher = patch("kiroshi_cloud_sync._ensure_directories")
        self.ensure_dirs_patcher.start()

        self.ensure_share_patcher = patch("kiroshi_cloud_sync.ensure_cloud_share")
        self.ensure_share_patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.ensure_dirs_patcher.stop()
        self.ensure_share_patcher.stop()
        shutil.rmtree(self.test_dir)

    def test_random_password_generation(self):
        """Verify that a random password is generated and logged."""

        # Capture stderr to verify logging
        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            config = kiroshi_cloud_sync.load_cloud_config(create_if_missing=True)

            output = mock_stderr.getvalue()
            self.assertIn("[SECURITY] Generated initial Kiroshi Cloud password:", output)

            # Extract the password from log
            generated_password = output.split("password: ")[1].split()[0]
            self.assertTrue(len(generated_password) > 10)

            # Verify hash matches
            salt = kiroshi_cloud_sync._decode_salt(config["password_salt"])
            expected_hash = kiroshi_cloud_sync._hash_password(generated_password, salt)
            self.assertEqual(config["password_hash"], expected_hash)

            # Verify it is flagged as default
            self.assertTrue(config["uses_default_credentials"])

    def test_env_var_override(self):
        """Verify that KIROSHI_INITIAL_ADMIN_PASSWORD overrides generation."""

        custom_password = "CorrectHorseBatteryStaple!"
        with patch.dict(os.environ, {"KIROSHI_INITIAL_ADMIN_PASSWORD": custom_password}):
            with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
                config = kiroshi_cloud_sync.load_cloud_config(create_if_missing=True)

                # Should NOT log generation message
                output = mock_stderr.getvalue()
                self.assertNotIn("Generated initial Kiroshi Cloud password", output)

                # Verify hash matches custom password
                salt = kiroshi_cloud_sync._decode_salt(config["password_salt"])
                expected_hash = kiroshi_cloud_sync._hash_password(custom_password, salt)
                self.assertEqual(config["password_hash"], expected_hash)

    def test_legacy_detection(self):
        """Verify that legacy 'admin123!' is detected."""

        # Manually create a config with legacy password
        salt_password = os.urandom(16)
        legacy_password = "admin123!"
        config = {
            "version": 2,
            "username": "admin",
            "password_salt": base64.urlsafe_b64encode(salt_password).decode("utf-8"),
            "password_hash": kiroshi_cloud_sync._hash_password(legacy_password, salt_password),
            "encryption_salt": "dummy",
            "uses_default_credentials": False, # Pretend user turned it off but password is still bad
            "instance_id": "test-id",
            "overlay_provider": "Test",
            "overlay_instructions": "Test",
        }

        # Direct check of the function first
        result = kiroshi_cloud_sync._synchronise_default_flag(config)
        self.assertTrue(result, "Function should return True indicating update")
        self.assertTrue(config["uses_default_credentials"], "Flag should be updated to True")

        # Now test via file loading
        # Reset flag
        config["uses_default_credentials"] = False
        with open(self.config_path, 'w') as f:
            json.dump(config, f)

        loaded_config = kiroshi_cloud_sync.load_cloud_config()
        self.assertTrue(loaded_config["uses_default_credentials"],
                        "Should detect legacy insecure password via load_cloud_config")

if __name__ == "__main__":
    unittest.main()
