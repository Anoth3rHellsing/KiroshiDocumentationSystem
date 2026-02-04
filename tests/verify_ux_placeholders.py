
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_dell_escalation_placeholders():
    """
    Static analysis to ensure Dell Escalation fields have help and placeholder text.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Fields we want to verify have both help and placeholder
    target_fields = {
        "dell_issue_start_date",
        "dell_command_updates_status",
        "dell_power_options_setup",
        "dell_optimizer_setup",
        "dell_intel_ppm_installed",
    }

    # Store findings: field -> set of found attributes
    found_attributes = {field: set() for field in target_fields}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for auto_text_input(...) calls
            if isinstance(node.func, ast.Name) and node.func.id == "auto_text_input":
                # Check args to find the field name (2nd argument)
                field_name = None
                if len(node.args) >= 2:
                    arg = node.args[1]
                    if isinstance(arg, ast.Constant): # python 3.8+
                        field_name = arg.value
                    elif hasattr(ast, "Str") and isinstance(arg, ast.Str): # older python
                        field_name = arg.s

                if field_name in target_fields:
                    # Check kwargs for help and placeholder
                    for kw in node.keywords:
                        if kw.arg in ("help", "placeholder"):
                            found_attributes[field_name].add(kw.arg)

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Verify all target fields have both attributes
    missing_info = {}
    for field, attributes in found_attributes.items():
        missing = []
        if "help" not in attributes:
            missing.append("help")
        if "placeholder" not in attributes:
            missing.append("placeholder")

        if missing:
            missing_info[field] = missing

    assert not missing_info, f"Missing attributes for Dell Escalation fields: {missing_info}"

if __name__ == "__main__":
    try:
        test_dell_escalation_placeholders()
        print("All target fields have help and placeholder attributes!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
