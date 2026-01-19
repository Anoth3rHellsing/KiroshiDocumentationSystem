
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_inputs_have_placeholders():
    """
    Static analysis to ensure critical text inputs have a 'placeholder' defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Fields we want to verify have placeholders
    target_fields = {
        "company_name",
        "subscription_id",
        "case_id",
        "brief_description",
        "caller_name",
        "phone_number",
        "email",
        "teamviewer_id",
        "teamviewer_password",
        "dongle_number"
    }

    # Store whether we found *at least one* instance of the input with a placeholder
    found_placeholders = {field: False for field in target_fields}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for auto_text_input(...) calls
            if isinstance(node.func, ast.Name) and node.func.id == "auto_text_input":
                # Extract field name (2nd arg)
                field_name = None
                if len(node.args) >= 2:
                    arg = node.args[1]
                    if isinstance(arg, ast.Constant): # python 3.8+
                        field_name = arg.value
                    elif hasattr(ast, "Str") and isinstance(arg, ast.Str): # older python
                        field_name = arg.s

                # Check kwargs if field not in args (unlikely based on usage, but good practice)
                if not field_name:
                    for kw in node.keywords:
                        if kw.arg == "field":
                            if isinstance(kw.value, ast.Constant):
                                field_name = kw.value.value
                            elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                                field_name = kw.value.s

                if field_name in target_fields:
                    has_placeholder = any(kw.arg == "placeholder" for kw in node.keywords)
                    if has_placeholder:
                        found_placeholders[field_name] = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Check findings
    missing_placeholders = [field for field, found in found_placeholders.items() if not found]

    assert not missing_placeholders, f"The following fields are missing placeholders in at least one instance: {missing_placeholders}"

if __name__ == "__main__":
    try:
        test_inputs_have_placeholders()
        print("All target inputs have placeholders!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
