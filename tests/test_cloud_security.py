import unittest
from unittest.mock import patch, MagicMock
import tempfile
import shutil
from pathlib import Path
import os
import json
import sys

# Add root to path
sys.path.append(os.getcwd())

import kiroshi_cloud_sync
from kiroshi_cloud_sync import (
    load_cloud_config,
    setup_cloud_config,
    CloudSetupRequiredError,
    CloudError
)

class TestCloudSecurity(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_path = Path(self.test_dir)
        self.config_path = self.test_path / "cloud_config.json"

        # Patch the paths in the module
        self.patcher_config = patch('kiroshi_cloud_sync.CLOUD_CONFIG_PATH', self.config_path)
        self.patcher_root = patch('kiroshi_cloud_sync.CLOUD_ROOT', self.test_path)
        self.patcher_db_root = patch('kiroshi_cloud_sync.DATABASE_ROOT', self.test_path / "db")
        self.patcher_db_utils = patch('kiroshi_cloud_sync.DATABASE_UTILITIES', self.test_path / "db/utils")
        self.patcher_ensure_share = patch('kiroshi_cloud_sync.ensure_cloud_share', return_value=self.test_path)

        self.patcher_config.start()
        self.patcher_root.start()
        self.patcher_db_root.start()
        self.patcher_db_utils.start()
        self.patcher_ensure_share.start()

    def tearDown(self):
        self.patcher_config.stop()
        self.patcher_root.stop()
        self.patcher_db_root.stop()
        self.patcher_db_utils.stop()
        self.patcher_ensure_share.stop()
        shutil.rmtree(self.test_dir)

    def test_load_config_missing_raises_setup_required(self):
        """Test that missing config raises CloudSetupRequiredError when create_if_missing is True."""
        # Ensure file does not exist
        if self.config_path.exists():
            self.config_path.unlink()

        with self.assertRaises(CloudSetupRequiredError):
            load_cloud_config(create_if_missing=True)

    def test_load_config_missing_raises_cloud_error(self):
        """Test that missing config raises CloudError when create_if_missing is False."""
        if self.config_path.exists():
            self.config_path.unlink()

        with self.assertRaises(CloudError):
            load_cloud_config(create_if_missing=False)

    def test_setup_cloud_config_creates_secure_config(self):
        """Test that setup_cloud_config creates a config with provided credentials."""
        username = "newadmin"
        password = "securepassword123"

        config = setup_cloud_config(username, password)

        self.assertTrue(self.config_path.exists())
        self.assertEqual(config["username"], username)
        self.assertFalse(config["uses_default_credentials"])
        self.assertIn("password_hash", config)
        self.assertIn("password_salt", config)

        # Verify we can load it back
        loaded_config = load_cloud_config()
        self.assertEqual(loaded_config["username"], username)

if __name__ == '__main__':
    unittest.main()
