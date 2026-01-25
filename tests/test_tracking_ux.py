
import ast
import os
import pytest
import sys

APP_PATH = "case_documentation_app.py"

def test_tracking_inputs_have_ux_hints():
    """
    Static analysis to ensure Tracking tab inputs have help tooltips and placeholders.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Inputs we want to verify
    # Format: (function_name, label_text, required_kwargs)
    targets = [
        ("text_input", "Service Tag", ["help", "placeholder"]),
        ("selectbox", "Tracking type", ["help"]),
        ("date_input", "Expected arrival date", ["help"]),
    ]

    found_targets = {label: False for _, label, _ in targets}
    satisfied_targets = {label: False for _, label, _ in targets}

    class UXVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Check for st.text_input, st.selectbox, etc.
            if isinstance(node.func, ast.Attribute) and hasattr(node.func, "attr"):
                func_name = node.func.attr

                # Check against our targets
                for target_func, target_label, required_kwargs in targets:
                    if func_name == target_func:
                        # Extract label
                        label = None
                        if node.args:
                            # Python 3.8+ ast.Constant, older ast.Str
                            arg0 = node.args[0]
                            if isinstance(arg0, ast.Constant):
                                label = arg0.value
                            elif hasattr(ast, "Str") and isinstance(arg0, ast.Str):
                                label = arg0.s

                        # Check kwargs if label not in args
                        if not label:
                            for kw in node.keywords:
                                if kw.arg == "label":
                                    if isinstance(kw.value, ast.Constant):
                                        label = kw.value.value
                                    elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                                        label = kw.value.s

                        if label == target_label:
                            found_targets[label] = True
                            # Check if all required kwargs are present
                            present_kwargs = {kw.arg for kw in node.keywords}
                            if all(req in present_kwargs for req in required_kwargs):
                                satisfied_targets[label] = True

            self.generic_visit(node)

    UXVisitor().visit(tree)

    # Check findings
    missing = [label for label, satisfied in satisfied_targets.items() if not satisfied]

    # We only fail if we FOUND the input but it lacked attributes.
    # If we didn't find the input at all, something else is wrong (renamed or removed),
    # but for this specific task we assume they exist.
    not_found = [label for label, found in found_targets.items() if not found]

    if not_found:
        pytest.fail(f"Could not find the following inputs in the code: {not_found}")

    assert not missing, f"The following inputs are missing UX attributes (help/placeholder): {missing}"

if __name__ == "__main__":
    try:
        test_tracking_inputs_have_ux_hints()
        print("All tracking inputs have required UX hints!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
