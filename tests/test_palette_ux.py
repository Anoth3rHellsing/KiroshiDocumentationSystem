import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_inputs_have_ux_hints():
    """
    Static analysis to ensure critical inputs have 'help' and 'placeholder' defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Fields we want to verify
    # (function_name, field_id) -> set of required kwargs
    targets = {
        ("auto_text_input", "brief_description"): {"help", "placeholder"},
        ("auto_text_area", "phone_description"): {"help", "placeholder"},
        ("auto_text_input", "caller_name"): {"help", "placeholder"},
    }

    found_targets = {key: set() for key in targets}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id

            if func_name in ["auto_text_input", "auto_text_area"]:
                # Extract field_id (2nd arg)
                field_id = None
                if len(node.args) >= 2:
                    if isinstance(node.args[1], ast.Constant):
                        field_id = node.args[1].value
                    elif isinstance(node.args[1], ast.Str):
                        field_id = node.args[1].s

                if not field_id:
                     # check kwargs
                    for kw in node.keywords:
                        if kw.arg == "field":
                            if isinstance(kw.value, ast.Constant):
                                field_id = kw.value.value
                            elif isinstance(kw.value, ast.Str):
                                field_id = kw.value.s

                key = (func_name, field_id)
                if key in targets:
                    for kw in node.keywords:
                        if kw.arg in targets[key]:
                            found_targets[key].add(kw.arg)

            self.generic_visit(node)

    InputVisitor().visit(tree)

    failures = []
    for key, required in targets.items():
        found = found_targets[key]
        missing = required - found
        if missing:
            failures.append(f"{key[0]}('{key[1]}') missing: {missing}")

    assert not failures, f"UX Check Failed: {failures}"
