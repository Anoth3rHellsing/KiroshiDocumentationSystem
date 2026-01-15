
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_settings_inputs_have_placeholders():
    """
    Static analysis to ensure Kiroshi Cloud settings inputs have 'placeholder' attributes.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Inputs we want to verify by their label/key
    target_inputs = {
        "kiroshi_cloud_username",
        "kiroshi_cloud_password",
        "kiroshi_cloud_token"
    }

    found_placeholders = {key: False for key in target_inputs}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for st.text_input(...) or st.text_area(...) calls
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("text_input", "text_area"):

                # Check for key in kwargs
                key_value = None
                for kw in node.keywords:
                    if kw.arg == "key":
                        if isinstance(kw.value, ast.Constant):
                            key_value = kw.value.value
                        elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                            key_value = kw.value.s

                if key_value in target_inputs:
                    has_placeholder = any(kw.arg == "placeholder" for kw in node.keywords)
                    if has_placeholder:
                        found_placeholders[key_value] = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Check findings
    missing_placeholders = [key for key, found in found_placeholders.items() if not found]

    assert not missing_placeholders, f"The following settings inputs are missing placeholders: {missing_placeholders}"

if __name__ == "__main__":
    try:
        test_settings_inputs_have_placeholders()
        print("All target inputs have placeholders!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
