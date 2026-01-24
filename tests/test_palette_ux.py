import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_palette_ux_improvements():
    """
    Static analysis to ensure specific UX improvements (tooltips, placeholders) are present.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Targets to verify
    # (function_name, label, required_args)
    targets = [
        ("auto_text_input", "Brief description", {"help", "placeholder"}),
        ("st.text_input", "Service Tag", {"help", "placeholder"}),
        ("st.date_input", "Expected arrival date", {"help"}),
        ("st.selectbox", "Tracking type", {"help"}),
    ]

    found_targets = {
        (func, label): {arg: False for arg in reqs}
        for func, label, reqs in targets
    }

    class UXVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                # Handle st.text_input etc.
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "st":
                    func_name = f"st.{node.func.attr}"

            if not func_name:
                self.generic_visit(node)
                return

            # Check label (first arg)
            label = None
            if node.args:
                if isinstance(node.args[0], ast.Constant):
                    label = node.args[0].value
                # Fallback for older python versions if needed, though 3.12 uses Constant
                elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str):
                    label = node.args[0].s

            # If label not in args, check kwargs
            if not label:
                for kw in node.keywords:
                    if kw.arg == "label":
                        if isinstance(kw.value, ast.Constant):
                            label = kw.value.value
                        elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                            label = kw.value.s

            # Check if this call matches one of our targets
            target_key = (func_name, label)
            if target_key in found_targets:
                reqs = found_targets[target_key]
                for kw in node.keywords:
                    if kw.arg in reqs:
                        reqs[kw.arg] = True

            self.generic_visit(node)

    UXVisitor().visit(tree)

    # Verify all requirements met
    failures = []
    for (func, label), reqs in found_targets.items():
        missing = [arg for arg, found in reqs.items() if not found]
        if missing:
            failures.append(f"{func}('{label}') missing: {', '.join(missing)}")

    assert not failures, f"UX Validation Failed:\n" + "\n".join(failures)

if __name__ == "__main__":
    try:
        test_palette_ux_improvements()
        print("Test passed!")
    except AssertionError as e:
        print(f"Test failed:\n{e}")
