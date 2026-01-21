import os
import ast

def test_default_openai_api_key_is_empty():
    def get_assigned_value(filename, var_name):
        with open(filename, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())

        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == var_name:
                        # We found the assignment. Now we need to evaluate the value.
                        # It is likely os.environ.get("OPENAI_API_KEY", "")
                        if isinstance(node.value, ast.Call):
                            # Check if it is os.environ.get
                            func = node.value.func
                            if isinstance(func, ast.Attribute) and func.attr == "get":
                                if isinstance(func.value, ast.Attribute) and func.value.attr == "environ":
                                    # It's os.environ.get. Check arguments.
                                    args = node.value.args
                                    if len(args) == 2:
                                        # Arg 0 should be "OPENAI_API_KEY"
                                        # Arg 1 should be ""
                                        if isinstance(args[1], ast.Constant) and args[1].value == "":
                                            return ""
                                        elif isinstance(args[1], ast.Constant):
                                            return args[1].value
        return None

    # Check case_documentation_app.py
    val_app = get_assigned_value("case_documentation_app.py", "DEFAULT_OPENAI_API_KEY")
    assert val_app == "", f"case_documentation_app.py: Expected empty string default, got {val_app}"

    # Check kiroshi_chat.py
    val_chat = get_assigned_value("kiroshi_chat.py", "DEFAULT_OPENAI_API_KEY")
    assert val_chat == "", f"kiroshi_chat.py: Expected empty string default, got {val_chat}"

def test_no_hardcoded_secrets_in_source():
    # Scan source files for the known leaked key pattern
    # We construct the prefix dynamically to avoid triggering secret scanners on this test file itself.
    # The leaked key started with standard OpenAI prefix.
    p1 = "sk"
    p2 = "-proj-"
    p3 = "uYyU"
    leaked_prefix = p1 + p2 + p3

    files_to_check = ["case_documentation_app.py", "kiroshi_chat.py"]

    for filename in files_to_check:
        with open(filename, "r", encoding="utf-8") as f:
            content = f.read()
            assert leaked_prefix not in content, f"Found potential hardcoded secret in {filename}"

if __name__ == "__main__":
    test_default_openai_api_key_is_empty()
    test_no_hardcoded_secrets_in_source()
    print("Security tests passed!")
