
import ast
import os
try:
    import pytest
except ImportError:
    class MockPytest:
        def skip(self, msg):
            print(f"SKIPPING: {msg}")
            exit(0)
    pytest = MockPytest()

APP_PATH = "case_documentation_app.py"

def test_buttons_have_tooltips():
    """
    Static analysis to ensure critical buttons have a 'help' tooltip defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Buttons we want to verify
    target_buttons = {
        "Save and track",
        "Close case & stop tracking",
        "Save",
        "Load"
    }

    # Store whether we found *at least one* instance of the button with a tooltip
    found_buttons = {btn: False for btn in target_buttons}

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

                # Check kwargs if label not in args
                if not label:
                    for kw in node.keywords:
                        if kw.arg == "label":
                            if isinstance(kw.value, ast.Constant):
                                label = kw.value.value
                            elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                                label = kw.value.s

                if label in target_buttons:
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
        test_buttons_have_tooltips()
        print("All target buttons have tooltips!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
