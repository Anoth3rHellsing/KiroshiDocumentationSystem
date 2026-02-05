
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

TARGET_FIELDS = {
    "Dell Command Updates status",
    "Power Options setup",
    "Dell Optimizer setup",
    "Intel Processor Power Management Utility installed?",
    "CPU Speed / Is CPU throttling?",
    "GPU Usage % (Integrated)",
    "GPU Usage % (Dedicated)",
    "CPU Utilization %",
    "Benchmark used and results",
    "Which GPU driver versions were tested?",
    "Can it launch simulation on Ultra Resolution? (If needed)",
    "Reliability Monitor and Event Viewer results",
    "Dell Diagnosis test results (ePSA tests included)",
    "Has Windows been reimaged?",
}

def test_dell_escalation_fields_have_ux_hints():
    """
    Static analysis to ensure Dell escalation fields have 'placeholder' and 'help' attributes.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    found_fields = {field: {"placeholder": False, "help": False} for field in TARGET_FIELDS}

    class FieldVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Check for auto_text_input or auto_text_area calls
            if isinstance(node.func, ast.Name) and node.func.id in ("auto_text_input", "auto_text_area"):
                # Extract label from args
                label = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant): # python 3.8+
                        label = node.args[0].value
                    elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str): # older python
                        label = node.args[0].s

                if label in TARGET_FIELDS:
                    has_help = any(kw.arg == "help" for kw in node.keywords)
                    has_placeholder = any(kw.arg == "placeholder" for kw in node.keywords)

                    if has_help:
                        found_fields[label]["help"] = True
                    if has_placeholder:
                        found_fields[label]["placeholder"] = True

            self.generic_visit(node)

    FieldVisitor().visit(tree)

    missing_ux = []
    for field, status in found_fields.items():
        missing = []
        if not status["placeholder"]:
            missing.append("placeholder")
        if not status["help"]:
            missing.append("help")

        if missing:
            missing_ux.append(f"Field '{field}' is missing: {', '.join(missing)}")

    assert not missing_ux, "UX Verification Failed:\n" + "\n".join(f"- {issue}" for issue in missing_ux)

if __name__ == "__main__":
    try:
        test_dell_escalation_fields_have_ux_hints()
        print("All target fields have placeholders and help text!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
