
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_insert_buttons_have_tooltips():
    """
    Static analysis to ensure 'Insert' action buttons have a 'help' tooltip defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Labels of the buttons we modified
    target_labels = {
        "Insert",
        "Insert into Additional Info"
    }

    findings = []

    class ButtonVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # The function being called is usually an Attribute (e.g. st.button, col.button)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "button":
                label = None
                # Extract label from args
                if node.args:
                    if isinstance(node.args[0], (ast.Constant, ast.Str)):
                         # Handle both py3.8+ Constant and older Str
                         val = getattr(node.args[0], "value", getattr(node.args[0], "s", None))
                         label = val

                # Extract label from kwargs if not in args
                if not label:
                    for kw in node.keywords:
                        if kw.arg == "label":
                            if isinstance(kw.value, (ast.Constant, ast.Str)):
                                val = getattr(kw.value, "value", getattr(kw.value, "s", None))
                                label = val

                if label in target_labels:
                    has_help = any(kw.arg == "help" for kw in node.keywords)
                    findings.append({
                        "label": label,
                        "line": node.lineno,
                        "has_help": has_help
                    })

            self.generic_visit(node)

    ButtonVisitor().visit(tree)

    # We expect 3 specific buttons to be found
    # 1x "Insert into Additional Info"
    # 2x "Insert" (one for AV, one for FW)

    assert len(findings) >= 3, f"Expected to find at least 3 'Insert' buttons, found {len(findings)}"

    failures = [f for f in findings if not f["has_help"]]

    if failures:
        failure_msg = "\n".join([f"Button '{f['label']}' at line {f['line']} is missing a tooltip" for f in failures])
        pytest.fail(f"Found buttons missing tooltips:\n{failure_msg}")

if __name__ == "__main__":
    try:
        test_insert_buttons_have_tooltips()
        print("All Insert buttons have tooltips!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
