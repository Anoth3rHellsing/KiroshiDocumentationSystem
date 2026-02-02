
import ast
import os
import sys

APP_PATH = "case_documentation_app.py"

def verify_ux_placeholders():
    """
    Statically analyzes case_documentation_app.py to ensure auto_text_input/area calls
    in render_phonecall_section have 'placeholder' and 'help' arguments.
    """
    if not os.path.exists(APP_PATH):
        print(f"Error: {APP_PATH} not found.")
        sys.exit(1)

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    target_function = "render_phonecall_section"

    # Map of label -> required args
    target_fields = {
        "Caller name": ["placeholder", "help"],
        "Caller issue description": ["placeholder", "help"],
        "Dongle number": ["placeholder", "help"],
        "Phone number": ["placeholder", "help"],
        "Customer email": ["placeholder", "help"],
        "TeamViewer ID": ["placeholder", "help"],
        "TeamViewer password": ["placeholder", "help"],
    }

    # Tracking what we found
    found_fields = {field: {"placeholder": False, "help": False} for field in target_fields}
    function_found = False

    class PhoneCallVisitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            nonlocal function_found
            if node.name == target_function:
                function_found = True
                # Only visit nodes inside this function
                for child in node.body:
                    self.visit_child_nodes(child)
                # Don't visit other functions
                return

        def visit_child_nodes(self, node):
            # Helper to recursively visit children of a statement in the function
            for field, value in ast.iter_fields(node):
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.AST):
                            self.visit(item)
                elif isinstance(value, ast.AST):
                    self.visit(value)

        def visit_Call(self, node):
            # Check for auto_text_input or auto_text_area calls
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id

            if func_name in ("auto_text_input", "auto_text_area"):
                # Get the label (first arg)
                label = None
                if node.args:
                    arg0 = node.args[0]
                    if isinstance(arg0, ast.Constant): # python 3.8+
                        label = arg0.value
                    elif hasattr(ast, "Str") and isinstance(arg0, ast.Str):
                        label = arg0.s

                if label in target_fields:
                    # Check keywords
                    for kw in node.keywords:
                        if kw.arg in target_fields[label]:
                            found_fields[label][kw.arg] = True

    visitor = PhoneCallVisitor()
    visitor.visit(tree)

    if not function_found:
        print(f"Error: Function '{target_function}' not found in {APP_PATH}.")
        sys.exit(1)

    errors = []
    for field, requirements in found_fields.items():
        missing = []
        if not requirements["placeholder"]:
            missing.append("placeholder")
        if not requirements["help"]:
            missing.append("help")

        if missing:
            errors.append(f"Field '{field}' is missing: {', '.join(missing)}")

    if errors:
        print("UX Verification Failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)

    print("UX Verification Passed: All target fields have placeholders and help text.")

if __name__ == "__main__":
    verify_ux_placeholders()
