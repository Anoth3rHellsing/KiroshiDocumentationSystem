
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_inputs_have_placeholders_and_help():
    """
    Static analysis to ensure critical inputs have 'placeholder' and 'help' attributes.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Inputs we want to verify (label -> required_attributes)
    target_inputs = {
        "Company name": {"placeholder", "help"},
        "Subscription ID": {"placeholder", "help"},
        "Case ID": {"placeholder", "help"},
        "Brief description": {"placeholder", "help"},
        "Caller name": {"placeholder", "help"},
        "Dongle number": {"placeholder", "help"},
        "Phone number": {"placeholder", "help"},
        "Customer email": {"placeholder", "help"},
        "TeamViewer ID": {"placeholder", "help"},
        "TeamViewer password": {"placeholder", "help"},
        "Caller issue description": {"placeholder", "help"}, # This one is auto_text_area
    }

    found_inputs = {label: set() for label in target_inputs}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Check for auto_text_input or auto_text_area calls
            if isinstance(node.func, ast.Name) and node.func.id in ("auto_text_input", "auto_text_area"):
                # Extract label (first arg)
                label = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant): # python 3.8+
                        label = node.args[0].value
                    elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str): # older python
                        label = node.args[0].s

                if label in target_inputs:
                    # Check keywords
                    for kw in node.keywords:
                        if kw.arg in target_inputs[label]:
                            found_inputs[label].add(kw.arg)

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Check findings
    missing_attributes = []
    for label, required in target_inputs.items():
        found = found_inputs[label]
        missing = required - found
        if missing:
            missing_attributes.append(f"'{label}' is missing {missing}")

    assert not missing_attributes, f"The following inputs are missing UX attributes:\n" + "\n".join(missing_attributes)

if __name__ == "__main__":
    try:
        test_inputs_have_placeholders_and_help()
        print("All target inputs have placeholders and help!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
