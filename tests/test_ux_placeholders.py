
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_inputs_have_ux_attributes():
    """
    Static analysis to ensure critical input fields have 'help' and 'placeholder' attributes.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Inputs we want to verify (Label -> required attributes)
    target_inputs = {
        "Brief description": {"help", "placeholder"},
        "Description": {"help", "placeholder"},
        "Helpjuice link": {"help", "placeholder"},
        "Logs / screenshots": {"help", "placeholder"},
        "Caller name": {"help", "placeholder"},
        "Caller issue description": {"help", "placeholder"},
        "Dongle number": {"help", "placeholder"},
        "Phone number": {"help", "placeholder"},
        "Customer email": {"help", "placeholder"},
        "TeamViewer ID": {"help", "placeholder"},
        "TeamViewer password": {"help", "placeholder"},
        "Root cause": {"help", "placeholder"},
        "Solution": {"help", "placeholder"},
        "Customer satisfaction survey URL": {"help", "placeholder"},
    }

    # Tracking what we found
    # Map label -> set of found attributes
    found_attributes = {label: set() for label in target_inputs}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for auto_text_input / auto_text_area calls
            if isinstance(node.func, ast.Name) and node.func.id in ("auto_text_input", "auto_text_area"):
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

                if label in target_inputs:
                    for kw in node.keywords:
                        if kw.arg in target_inputs[label]:
                            found_attributes[label].add(kw.arg)

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Check findings
    failures = []
    for label, required in target_inputs.items():
        found = found_attributes[label]
        missing = required - found
        if missing:
            failures.append(f"Field '{label}' is missing attributes: {missing}")

    assert not failures, "\n".join(failures)

if __name__ == "__main__":
    try:
        test_inputs_have_ux_attributes()
        print("All target inputs have required UX attributes!")
    except AssertionError as e:
        print(f"Test failed:\n{e}")
    except Exception as e:
        print(f"An error occurred: {e}")
