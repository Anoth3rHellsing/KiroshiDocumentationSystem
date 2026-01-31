import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_tutorial_buttons_have_tooltips():
    """
    Static analysis to ensure tutorial and installer buttons have a 'help' tooltip defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Buttons we want to verify
    # Keys are the labels (or placeholder for dynamic label)
    found_buttons = {
        "Skip tutorial": False,
        "Back": False,
        "Run Kiroshi Installer": False,
        "Validar conexión": False,
        "next_label_placeholder": False
    }

    class ButtonVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for st.button(...) calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == "button":
                # Extract label from args or kwargs
                label = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant): # python 3.8+
                        label = node.args[0].value
                    elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str): # older python
                        label = node.args[0].s
                    elif isinstance(node.args[0], ast.Name) and node.args[0].id == "next_label":
                        label = "next_label_placeholder"

                # Check kwargs if label not in args
                if not label:
                    for kw in node.keywords:
                        if kw.arg == "label":
                            if isinstance(kw.value, ast.Constant):
                                label = kw.value.value
                            elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                                label = kw.value.s
                            elif isinstance(kw.value, ast.Name) and kw.value.id == "next_label":
                                label = "next_label_placeholder"

                if label in found_buttons:
                    has_help = any(kw.arg == "help" for kw in node.keywords)
                    if has_help:
                        found_buttons[label] = True

            self.generic_visit(node)

    ButtonVisitor().visit(tree)

    # Check findings
    missing_tooltips = [btn for btn, found in found_buttons.items() if not found]

    assert not missing_tooltips, f"The following buttons are missing tooltips in at least one instance: {missing_tooltips}"

if __name__ == "__main__":
    try:
        test_tutorial_buttons_have_tooltips()
        print("All target buttons have tooltips!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
