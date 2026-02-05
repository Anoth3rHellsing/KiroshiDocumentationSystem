
import ast
import sys
import unittest
from unittest.mock import MagicMock
import secrets
import os

class SecurityVerify(unittest.TestCase):
    def setUp(self):
        # Read the file
        app_path = os.path.join(os.path.dirname(__file__), "..", "case_documentation_app.py")
        with open(app_path, "r", encoding="utf-8") as f:
            self.tree = ast.parse(f.read())

        # Find render_debug_panel function
        self.render_debug_panel_def = None
        for node in self.tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "render_debug_panel":
                self.render_debug_panel_def = node
                break

        if not self.render_debug_panel_def:
            self.fail("Could not find render_debug_panel function")

        # Compile the function
        module_ast = ast.Module(body=[self.render_debug_panel_def], type_ignores=[])
        self.code = compile(module_ast, filename="<ast>", mode="exec")

        self.namespace = {
            "st": MagicMock(),
            "global_widget_key": lambda x: x,
            "get_session_state_snapshot": MagicMock(),
            "log_path": None,
            "LOG_FILE": "app.log",
            "tail_log": MagicMock(),
            "active_category_map": MagicMock(),
            "render_autohotkey_panel": MagicMock(),
            "_resolve_hotkey_target_index": MagicMock(return_value=0),
            "_case_display_name": MagicMock(return_value="Case 1"),
            "CURRENT_CASE_IDX": 0,
            "HOTKEY_TARGET_SESSION_KEY": "hotkey_target",
            "_refresh_hotkey_snapshot": MagicMock(),
            "logging": MagicMock(),
            "Sequence": list,
            "secrets": secrets, # Make secrets available
        }

        self.namespace["st"].session_state = MagicMock()
        self.namespace["st"].session_state.debug_auth = False
        self.namespace["st"].session_state.get.return_value = False


    def test_default_credentials(self):
        # Simulate defaults
        self.namespace["DEBUG_USERNAME"] = "admin"
        self.namespace["DEBUG_PASSWORD"] = "admin"

        self.namespace["st"].text_input.side_effect = ["admin", "admin"]
        self.namespace["st"].button.return_value = True

        exec(self.code, self.namespace)
        self.namespace["render_debug_panel"]()

        self.assertTrue(self.namespace["st"].session_state.debug_auth, "Should login with default admin/admin")

    def test_invalid_credentials(self):
        self.namespace["DEBUG_USERNAME"] = "admin"
        self.namespace["DEBUG_PASSWORD"] = "admin"

        self.namespace["st"].text_input.side_effect = ["admin", "wrong"]
        self.namespace["st"].button.return_value = True

        exec(self.code, self.namespace)
        self.namespace["render_debug_panel"]()

        self.assertFalse(self.namespace["st"].session_state.debug_auth, "Should not login with wrong password")
        self.namespace["st"].error.assert_called_with("Invalid credentials")

    def test_custom_credentials(self):
        # Simulate env var override (by setting the constants)
        self.namespace["DEBUG_USERNAME"] = "superadmin"
        self.namespace["DEBUG_PASSWORD"] = "securepass"

        self.namespace["st"].text_input.side_effect = ["superadmin", "securepass"]
        self.namespace["st"].button.return_value = True

        exec(self.code, self.namespace)
        self.namespace["render_debug_panel"]()

        self.assertTrue(self.namespace["st"].session_state.debug_auth, "Should login with custom credentials")

    def test_custom_credentials_fail(self):
        self.namespace["DEBUG_USERNAME"] = "superadmin"
        self.namespace["DEBUG_PASSWORD"] = "securepass"

        self.namespace["st"].text_input.side_effect = ["admin", "admin"]
        self.namespace["st"].button.return_value = True

        exec(self.code, self.namespace)
        self.namespace["render_debug_panel"]()

        self.assertFalse(self.namespace["st"].session_state.debug_auth, "Should not login with old defaults if custom are set")


if __name__ == "__main__":
    unittest.main()
