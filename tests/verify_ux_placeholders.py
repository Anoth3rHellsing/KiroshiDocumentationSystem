import ast
import os
import sys

APP_PATH = "case_documentation_app.py"

def verify_phonecall_placeholders():
    """
    Static analysis to ensure 'render_phonecall_section' inputs have 'placeholder' and 'help' defined.
    """
    if not os.path.exists(APP_PATH):
        print(f"{APP_PATH} not found")
        sys.exit(1)

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    class PhonecallVisitor(ast.NodeVisitor):
        def __init__(self):
            self.in_render_phonecall = False
            self.issues = []

        def visit_FunctionDef(self, node):
            if node.name == "render_phonecall_section":
                self.in_render_phonecall = True
                self.generic_visit(node)
                self.in_render_phonecall = False
            else:
                # Don't visit other functions
                pass

        def visit_Call(self, node):
            if not self.in_render_phonecall:
                return

            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id

            if func_name in ["auto_text_input", "auto_text_area"]:
                # Get the label (first arg)
                label = "Unknown"
                if node.args:
                    if isinstance(node.args[0], ast.Constant):
                        label = node.args[0].value
                    elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str):
                        label = node.args[0].s

                # Check for keywords
                has_placeholder = False
                has_help = False

                for kw in node.keywords:
                    if kw.arg == "placeholder":
                        has_placeholder = True
                    if kw.arg == "help":
                        has_help = True

                if not has_placeholder:
                    self.issues.append(f"Missing 'placeholder' for '{label}' in {func_name}")
                if not has_help:
                    self.issues.append(f"Missing 'help' for '{label}' in {func_name}")

            self.generic_visit(node)

    visitor = PhonecallVisitor()
    visitor.visit(tree)

    if visitor.issues:
        print("UX Verification Failed:")
        for issue in visitor.issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        print("UX Verification Passed: All inputs in render_phonecall_section have placeholders and help text.")

if __name__ == "__main__":
    verify_phonecall_placeholders()
