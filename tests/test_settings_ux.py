
import ast
import os
import pytest
import sys

APP_PATH = "case_documentation_app.py"

def test_settings_inputs_have_placeholders():
    """
    Static analysis to ensure critical settings inputs have a 'placeholder' defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Inputs we want to verify
    target_inputs = {
        "Usuario del cloud",
        "Contraseña del cloud",
        "Token de conexión del dispositivo"
    }

    # Store whether we found *at least one* instance of the input with a placeholder
    found_placeholders = {label: False for label in target_inputs}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for st.text_input(...) or st.text_area(...) calls
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("text_input", "text_area"):
                # Extract label from args or kwargs
                label = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant): # python 3.8+
                        label = node.args[0].value
                    elif sys.version_info < (3, 14) and hasattr(ast, "Str") and isinstance(node.args[0], ast.Str): # older python compat
                        label = node.args[0].s

                # Check kwargs if label not in args
                if not label:
                    for kw in node.keywords:
                        if kw.arg == "label":
                            if isinstance(kw.value, ast.Constant):
                                label = kw.value.value
                            elif sys.version_info < (3, 14) and hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                                label = kw.value.s

                if label in target_inputs:
                    has_placeholder = any(kw.arg == "placeholder" for kw in node.keywords)
                    if has_placeholder:
                        found_placeholders[label] = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Check findings
    missing_placeholders = [label for label, found in found_placeholders.items() if not found]

    assert not missing_placeholders, f"The following inputs are missing placeholders: {missing_placeholders}"

if __name__ == "__main__":
    try:
        test_settings_inputs_have_placeholders()
        print("All target inputs have placeholders!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
