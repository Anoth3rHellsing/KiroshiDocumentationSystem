import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

TARGET_FIELDS = {
    "Company name": {"placeholder", "help"},
    "Subscription ID": {"placeholder", "help"},
    "Case ID": {"placeholder", "help"},
    "Brief description": {"placeholder", "help"},
    "Caller name": {"placeholder", "help"},
    "Caller issue description": {"placeholder", "help"},
    "Dongle number": {"placeholder", "help"},
    "Phone number": {"placeholder", "help"},
    "Customer email": {"placeholder", "help"},
    "TeamViewer ID": {"placeholder", "help"},
    "TeamViewer password": {"placeholder", "help"},
    "Description": {"placeholder", "help"},
    "Root cause": {"placeholder", "help"},
    "Solution": {"placeholder", "help"},
    "Customer satisfaction survey URL": {"placeholder", "help"},
    "Reseller case # (Straumann / Patterson)": {"placeholder", "help"},
}

def test_ux_placeholders_and_help():
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    found_attributes = {field: set() for field in TARGET_FIELDS}

    class FieldVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in ["auto_text_input", "auto_text_area", "text_input"]:
                label = None
                if node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant):
                        label = arg0.value
                    elif isinstance(arg0, ast.Str): # Python < 3.8
                        label = arg0.s

                if label in TARGET_FIELDS:
                    for kw in node.keywords:
                        if kw.arg in ["placeholder", "help"]:
                            found_attributes[label].add(kw.arg)

            self.generic_visit(node)

    FieldVisitor().visit(tree)

    missing_info = []
    for field, required_attrs in TARGET_FIELDS.items():
        found = found_attributes[field]
        missing = required_attrs - found
        if missing:
            missing_info.append(f"{field}: missing {missing}")

    assert not missing_info, f"Missing UX attributes:\n" + "\n".join(missing_info)

if __name__ == "__main__":
    try:
        test_ux_placeholders_and_help()
        print("All target fields have placeholders and help text!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
