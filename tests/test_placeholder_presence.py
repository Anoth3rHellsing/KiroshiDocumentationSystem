
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_inputs_have_placeholders():
    """
    Static analysis to ensure critical inputs have a 'placeholder' defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Fields we want to verify (second arg of auto_text_input)
    target_fields = {
        "brief_description",
        "caller_name",
        "phone_number"
    }

    # Store whether we found *at least one* instance of the field with a placeholder
    found_fields = {field: False for field in target_fields}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for auto_text_input(...) calls
            if isinstance(node.func, ast.Name) and node.func.id == "auto_text_input":
                # Extract field name from args (position 1)
                field_name = None
                if len(node.args) > 1:
                    # Arg 0 is label, Arg 1 is field
                    arg_val = node.args[1]
                    if isinstance(arg_val, ast.Constant): # python 3.8+
                        field_name = arg_val.value
                    elif hasattr(ast, "Str") and isinstance(arg_val, ast.Str): # older python
                        field_name = arg_val.s

                if field_name in target_fields:
                    has_placeholder = any(kw.arg == "placeholder" for kw in node.keywords)
                    if has_placeholder:
                        found_fields[field_name] = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Check findings
    missing_placeholders = [field for field, found in found_fields.items() if not found]

    assert not missing_placeholders, f"The following fields are missing placeholders in at least one instance: {missing_placeholders}"

if __name__ == "__main__":
    try:
        test_inputs_have_placeholders()
        print("All target inputs have placeholders!")
    except AssertionError as e:
        print(f"Test failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
