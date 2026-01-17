
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_inputs_have_placeholders():
    """
    Static analysis to ensure critical inputs have a 'placeholder' attribute defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Inputs we want to verify have placeholders
    # Maps field_name (2nd arg) to found status
    target_fields = {
        "brief_description": False,
        "caller_name": False,
        "phone_number": False,
    }

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for auto_text_input(...) calls
            if isinstance(node.func, ast.Name) and node.func.id == "auto_text_input":
                # We need to find the second argument which is 'field'
                field_name = None

                # Check positional args (label, field)
                if len(node.args) >= 2:
                    arg = node.args[1]
                    if isinstance(arg, ast.Constant): # python 3.8+
                        field_name = arg.value
                    elif hasattr(ast, "Str") and isinstance(arg, ast.Str): # older python
                        field_name = arg.s

                # If not found in positional, check kwargs
                if not field_name:
                    for kw in node.keywords:
                        if kw.arg == "field":
                            if isinstance(kw.value, ast.Constant):
                                field_name = kw.value.value
                            elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                                field_name = kw.value.s

                if field_name in target_fields:
                    has_placeholder = any(kw.arg == "placeholder" for kw in node.keywords)
                    if has_placeholder:
                        target_fields[field_name] = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Check findings
    missing_placeholders = [field for field, found in target_fields.items() if not found]

    assert not missing_placeholders, f"The following fields are missing placeholders: {missing_placeholders}"

if __name__ == "__main__":
    try:
        test_inputs_have_placeholders()
        print("All target inputs have placeholders!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
