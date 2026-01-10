import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"
CHAT_PATH = "kiroshi_chat.py"
KEY_PATTERN = "sk-proj-"

def check_for_secrets(filepath):
    if not os.path.exists(filepath):
        pytest.skip(f"{filepath} not found")

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    tree = ast.parse(content)

    class SecretVisitor(ast.NodeVisitor):
        def __init__(self):
            self.found_secrets = []

        def visit_Assign(self, node):
            # Check for DEFAULT_OPENAI_API_KEY assignment
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEFAULT_OPENAI_API_KEY":
                    # Check if the value assigned contains the secret pattern
                    # Handle direct string assignment: DEFAULT_OPENAI_API_KEY = "sk-..."
                    if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                        if KEY_PATTERN in node.value.value:
                            self.found_secrets.append(f"Direct assignment in {filepath} line {node.lineno}")
                    elif hasattr(ast, "Str") and isinstance(node.value, ast.Str): # Python < 3.8
                         if KEY_PATTERN in node.value.s:
                            self.found_secrets.append(f"Direct assignment in {filepath} line {node.lineno}")

                    # Handle os.environ.get(..., "sk-...")
                    elif isinstance(node.value, ast.Call):
                         for arg in node.value.args:
                            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                 if KEY_PATTERN in arg.value:
                                     self.found_secrets.append(f"Default value in os.environ.get in {filepath} line {node.lineno}")
                            elif hasattr(ast, "Str") and isinstance(arg, ast.Str):
                                if KEY_PATTERN in arg.s:
                                     self.found_secrets.append(f"Default value in os.environ.get in {filepath} line {node.lineno}")
            self.generic_visit(node)

    visitor = SecretVisitor()
    visitor.visit(tree)
    return visitor.found_secrets

def test_no_hardcoded_secrets_in_app():
    secrets = check_for_secrets(APP_PATH)
    assert not secrets, f"Found secrets in {APP_PATH}: {secrets}"

def test_no_hardcoded_secrets_in_chat():
    secrets = check_for_secrets(CHAT_PATH)
    assert not secrets, f"Found secrets in {CHAT_PATH}: {secrets}"

if __name__ == "__main__":
    # Manually run the checks if executed directly
    try:
        test_no_hardcoded_secrets_in_app()
        print(f"✅ {APP_PATH} passed secret check")
    except AssertionError as e:
        print(f"❌ {APP_PATH} failed secret check: {e}")

    try:
        test_no_hardcoded_secrets_in_chat()
        print(f"✅ {CHAT_PATH} passed secret check")
    except AssertionError as e:
        print(f"❌ {CHAT_PATH} failed secret check: {e}")
