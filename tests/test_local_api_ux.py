
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_api_key_input_has_help():
    """
    Static analysis to ensure the 'API Key (optional)' text input has a 'help' tooltip.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    found_input = False
    has_help = False

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            nonlocal found_input, has_help
            # Look for st.text_input(...) calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == "text_input":
                # Extract label
                label = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant): # python 3.8+
                        label = node.args[0].value
                    elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str):
                        label = node.args[0].s

                # Check label match
                if label == "API Key (optional)":
                    found_input = True
                    # Check for help argument
                    if any(kw.arg == "help" for kw in node.keywords):
                        has_help = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    assert found_input, "Could not find 'API Key (optional)' text input in the code."
    assert has_help, "'API Key (optional)' text input is missing a 'help' tooltip."

if __name__ == "__main__":
    try:
        test_api_key_input_has_help()
        print("Test passed!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
