import ast
import os
import sys

def test_no_hardcoded_secrets_default():
    """Verify that DEFAULT_OPENAI_API_KEY is not a hardcoded secret string."""
    with open("case_documentation_app.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    found_default = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEFAULT_OPENAI_API_KEY":
                    # Found assignment, check the value
                    if isinstance(node.value, ast.Call):
                        # Should be os.environ.get(...)
                        func = node.value.func
                        if isinstance(func, ast.Attribute) and func.attr == "get":
                            # Check arguments
                            args = node.value.args
                            if len(args) >= 2:
                                default_val = args[1]
                                if isinstance(default_val, ast.Constant):
                                    assert default_val.value == "", "DEFAULT_OPENAI_API_KEY default must be empty string"
                                    found_default = True
                                elif isinstance(default_val, ast.Str): # legacy
                                    assert default_val.s == "", "DEFAULT_OPENAI_API_KEY default must be empty string"
                                    found_default = True

    assert found_default, "Could not find DEFAULT_OPENAI_API_KEY assignment in proper format"

def test_kiroshi_chat_no_hardcoded_secrets():
    """Verify that DEFAULT_OPENAI_API_KEY in kiroshi_chat.py is not hardcoded."""
    with open("kiroshi_chat.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    found_default = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "DEFAULT_OPENAI_API_KEY":
                    if isinstance(node.value, ast.Call):
                         # Should be os.environ.get(...)
                        func = node.value.func
                        if isinstance(func, ast.Attribute) and func.attr == "get":
                             args = node.value.args
                             if len(args) >= 2:
                                default_val = args[1]
                                if isinstance(default_val, ast.Constant):
                                    assert default_val.value == "", "DEFAULT_OPENAI_API_KEY default must be empty string"
                                    found_default = True
                                elif isinstance(default_val, ast.Str):
                                    assert default_val.s == "", "DEFAULT_OPENAI_API_KEY default must be empty string"
                                    found_default = True
    assert found_default, "Could not find DEFAULT_OPENAI_API_KEY assignment in kiroshi_chat.py"
