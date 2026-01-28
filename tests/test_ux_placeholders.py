import ast
import os
import sys
import pytest

APP_PATH = "case_documentation_app.py"

def test_ux_placeholders():
    """
    Static analysis to ensure specific input fields have 'help' and 'placeholder' defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Fields we want to verify
    target_fields = {
        "Agent name",
        "Spare item description",
        "Serial number of the device being replaced"
    }

    # Store findings: field_label -> {'help': bool, 'placeholder': bool}
    findings = {label: {'help': False, 'placeholder': False} for label in target_fields}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for st.text_input(...) calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == "text_input":
                # Extract label from args or kwargs
                label = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant): # python 3.8+
                        label = node.args[0].value
                    elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str): # older python
                        label = node.args[0].s

                # Check kwargs if label not in args
                if not label:
                    for kw in node.keywords:
                        if kw.arg == "label":
                            if isinstance(kw.value, ast.Constant):
                                label = kw.value.value
                            elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                                label = kw.value.s

                if label in target_fields:
                    has_help = any(kw.arg == "help" for kw in node.keywords)
                    has_placeholder = any(kw.arg == "placeholder" for kw in node.keywords)

                    if has_help:
                        findings[label]['help'] = True
                    if has_placeholder:
                        findings[label]['placeholder'] = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Check findings
    missing_attributes = []
    for label, attributes in findings.items():
        if not attributes['help']:
            missing_attributes.append(f"'{label}' missing help")
        if not attributes['placeholder']:
            missing_attributes.append(f"'{label}' missing placeholder")

    assert not missing_attributes, f"UX Validation Failed: {', '.join(missing_attributes)}"

if __name__ == "__main__":
    test_ux_placeholders()
