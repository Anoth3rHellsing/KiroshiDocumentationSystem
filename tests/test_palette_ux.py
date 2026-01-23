
import ast
import os
import sys

APP_PATH = "case_documentation_app.py"

def test_fields_have_ux_hints():
    """
    Static analysis to ensure critical input fields have 'help' and 'placeholder' defined.
    """
    if not os.path.exists(APP_PATH):
        print(f"{APP_PATH} not found")
        sys.exit(1)

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Fields we want to verify (field_name -> required_attributes)
    target_fields = {
        "brief_description": {"help", "placeholder"},
        "caller_name": {"help", "placeholder"},
        "phone_description": {"help", "placeholder"},
    }

    # Tracking findings
    findings = {field: set() for field in target_fields}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # We are looking for calls to auto_text_input or auto_text_area
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id

            if func_name in ("auto_text_input", "auto_text_area"):
                # The second argument is the field name (e.g. "brief_description")
                # def auto_text_input(label, field, ...)
                if len(node.args) >= 2:
                    field_arg = node.args[1]
                    field_name = None
                    if isinstance(field_arg, ast.Constant): # python 3.8+
                        field_name = field_arg.value
                    elif hasattr(ast, "Str") and isinstance(field_arg, ast.Str):
                        field_name = field_arg.s

                    if field_name in target_fields:
                        # Check keywords for help and placeholder
                        for kw in node.keywords:
                            if kw.arg in target_fields[field_name]:
                                findings[field_name].add(kw.arg)

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Validate findings
    failed = False
    for field, requirements in target_fields.items():
        missing = requirements - findings[field]
        if missing:
            print(f"❌ Field '{field}' is missing UX attributes: {missing}")
            failed = True
        else:
            print(f"✅ Field '{field}' has all required UX attributes.")

    if failed:
        sys.exit(1)

if __name__ == "__main__":
    test_fields_have_ux_hints()
