import ast
import os
import pytest
import sys

APP_PATH = "case_documentation_app.py"

def test_critical_fields_have_ux_hints():
    """
    Static analysis to ensure critical input fields have 'placeholder' and 'help' attributes.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    failures = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check for auto_text_input("Brief description", ...)
            if (isinstance(node.func, ast.Name) and node.func.id == "auto_text_input") or \
               (isinstance(node.func, ast.Attribute) and node.func.attr == "auto_text_input"):

                args = [arg.value for arg in node.args if isinstance(arg, ast.Constant)]
                if not args and node.args and hasattr(node.args[0], 's'):
                     args = [arg.s for arg in node.args if isinstance(arg, ast.Str)]

                # Check args for label or field name
                if len(node.args) >= 2:
                    arg1 = node.args[0]
                    arg2 = node.args[1]
                    val1 = arg1.value if isinstance(arg1, ast.Constant) else None
                    val2 = arg2.value if isinstance(arg2, ast.Constant) else None

                    if val1 == "Brief description" or val2 == "brief_description":
                        keywords = [k.arg for k in node.keywords]
                        if "placeholder" not in keywords:
                            failures.append("Brief description missing placeholder")
                        if "help" not in keywords:
                            failures.append("Brief description missing help")

                    if val1 == "Caller name" or val2 == "caller_name":
                        keywords = [k.arg for k in node.keywords]
                        if "placeholder" not in keywords:
                            failures.append("Caller name missing placeholder")
                        if "help" not in keywords:
                            failures.append("Caller name missing help")

            # Check for auto_text_area("Caller issue description", "phone_description", ...)
            if (isinstance(node.func, ast.Name) and node.func.id == "auto_text_area"):
                if len(node.args) >= 2:
                    arg1 = node.args[0]
                    arg2 = node.args[1]
                    val1 = arg1.value if isinstance(arg1, ast.Constant) else None
                    val2 = arg2.value if isinstance(arg2, ast.Constant) else None

                    if val1 == "Caller issue description" or val2 == "phone_description":
                        keywords = [k.arg for k in node.keywords]
                        if "placeholder" not in keywords:
                            failures.append("Caller issue description missing placeholder")
                        if "help" not in keywords:
                            failures.append("Caller issue description missing help")

    if failures:
        pytest.fail(f"UX Validation Failed: {', '.join(failures)}")

if __name__ == "__main__":
    # Allow running directly
    try:
        test_critical_fields_have_ux_hints()
        print("All UX checks passed!")
    except Exception as e:
        print(e)
        sys.exit(1)
