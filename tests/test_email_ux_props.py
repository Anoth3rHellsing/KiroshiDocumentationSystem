import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_email_inputs_have_help_and_placeholder():
    """
    Static analysis to ensure specific Email tab inputs have 'help' and 'placeholder' defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Inputs we want to verify (label text -> required attributes)
    target_inputs = {
        "Reason for contacting the customer": {"help", "placeholder"},
        "Goal of the email": {"help", "placeholder"},
        "What do we need from the customer?": {"help", "placeholder"},
        "User instructions": {"help", "placeholder"},
    }

    # Tracking findings
    found_inputs = {label: {"help": False, "placeholder": False} for label in target_inputs}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for st.text_input(...) or st.text_area(...) calls
            if isinstance(node.func, ast.Attribute) and node.func.attr in ("text_input", "text_area"):
                # Extract label
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
                    required_attrs = target_inputs[label]
                    for kw in node.keywords:
                        if kw.arg in required_attrs:
                            found_inputs[label][kw.arg] = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Validate results
    failures = []
    for label, requirements in target_inputs.items():
        found = found_inputs[label]
        missing = [req for req in requirements if not found[req]]
        if missing:
            failures.append(f"Input '{label}' is missing attributes: {', '.join(missing)}")

    assert not failures, "\n".join(failures)

if __name__ == "__main__":
    try:
        test_email_inputs_have_help_and_placeholder()
        print("All target email inputs have required UX properties!")
    except AssertionError as e:
        print(f"Test failed:\n{e}")
    except Exception as e:
        print(f"An error occurred: {e}")
