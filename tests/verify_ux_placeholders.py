
import ast
import os
import sys

APP_PATH = "case_documentation_app.py"

def verify_placeholders_and_tooltips():
    """
    Static analysis to ensure 'render_phonecall_section' inputs have 'placeholder' and 'help'.
    """
    if not os.path.exists(APP_PATH):
        print(f"{APP_PATH} not found")
        sys.exit(1)

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Fields we want to verify in render_phonecall_section
    target_fields = {
        "Caller name",
        "Dongle number",
        "Phone number",
        "Customer email",
        "TeamViewer ID",
        "TeamViewer password"
    }

    # Tracking findings
    found_fields = {field: {"placeholder": False, "help": False} for field in target_fields}

    class PhoneCallVisitor(ast.NodeVisitor):
        def __init__(self):
            self.in_render_function = False

        def visit_FunctionDef(self, node):
            if node.name == "render_phonecall_section":
                self.in_render_function = True
                self.generic_visit(node)
                self.in_render_function = False
            else:
                # Don't visit other functions
                pass

        def visit_Call(self, node):
            if not self.in_render_function:
                return

            # Check for auto_text_input("Label", ...)
            if isinstance(node.func, ast.Name) and node.func.id == "auto_text_input":
                # Extract label from first arg
                label = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant): # python 3.8+
                        label = node.args[0].value
                    elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str): # older python
                        label = node.args[0].s

                if label in target_fields:
                    # Check keywords
                    for kw in node.keywords:
                        if kw.arg == "placeholder":
                            found_fields[label]["placeholder"] = True
                        if kw.arg == "help":
                            found_fields[label]["help"] = True

            self.generic_visit(node)

    PhoneCallVisitor().visit(tree)

    # Check findings
    failures = []
    for field, status in found_fields.items():
        if not status["placeholder"]:
            failures.append(f"Missing placeholder for '{field}'")
        if not status["help"]:
            failures.append(f"Missing help for '{field}'")

    if failures:
        print("Verification Failed:")
        for fail in failures:
            print(f"- {fail}")
        sys.exit(1)
    else:
        print("Verification Passed: All target fields have placeholders and tooltips.")

if __name__ == "__main__":
    verify_placeholders_and_tooltips()
