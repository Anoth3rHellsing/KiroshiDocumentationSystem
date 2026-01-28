
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_inputs_have_placeholders():
    """
    Static analysis to ensure critical inputs in the Case Header have placeholders and tooltips.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Inputs we want to verify
    # Map label -> requirements dict
    target_inputs = {
        "Reseller case # (Straumann / Patterson)": {"placeholder": True, "help": True},
        "Company name": {"placeholder": True},
        "Subscription ID": {"placeholder": True},
        "Case ID": {"placeholder": True},
        "Brief description": {"placeholder": True},
    }

    # Store findings
    findings = {label: {"placeholder": False, "help": False} for label in target_inputs}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Check for text_input (including card.text_input) or auto_text_input
            func_name = None
            if isinstance(node.func, ast.Attribute):
                if node.func.attr in ["text_input", "auto_text_input"]:
                    func_name = node.func.attr
            elif isinstance(node.func, ast.Name):
                if node.func.id in ["text_input", "auto_text_input"]:
                    func_name = node.func.id

            if func_name:
                # Extract label
                label = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant): # python 3.8+
                        label = node.args[0].value
                    elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str):
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
                    # Check for keywords
                    for kw in node.keywords:
                        if kw.arg == "placeholder":
                            findings[label]["placeholder"] = True
                        if kw.arg == "help":
                            findings[label]["help"] = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Verify requirements
    failures = []
    for label, requirements in target_inputs.items():
        if requirements.get("placeholder") and not findings[label]["placeholder"]:
            failures.append(f"Missing placeholder for '{label}'")
        if requirements.get("help") and not findings[label]["help"]:
            failures.append(f"Missing help tooltip for '{label}'")

    assert not failures, f"UX Validation Failed:\n" + "\n".join(failures)

if __name__ == "__main__":
    try:
        test_inputs_have_placeholders()
        print("All target inputs have required UX attributes!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
