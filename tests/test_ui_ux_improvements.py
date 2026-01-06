import ast
import sys

def test_saved_cases_ux_present():
    """Verify that the Saved Cases page includes the Clear Filters UX improvement."""
    with open("case_documentation_app.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Check for _reset_saved_cases_filters function definition
    reset_func_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_reset_saved_cases_filters":
            reset_func_found = True
            break

    assert reset_func_found, "Function _reset_saved_cases_filters not found in case_documentation_app.py"

    # Check for Clear Filters button usage
    button_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check for st.button("Clear Filters", ...)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "button":
                if node.args and isinstance(node.args[0], (ast.Str, ast.Constant)): # Handle python < 3.8 and >= 3.8
                    arg_val = node.args[0].s if isinstance(node.args[0], ast.Str) else node.args[0].value
                    if arg_val == "Clear Filters":
                        button_found = True
                        break

    assert button_found, "Button 'Clear Filters' not found in case_documentation_app.py"
    print("UX Verification Passed: Clear Filters button and handler are present.")

if __name__ == "__main__":
    test_saved_cases_ux_present()
