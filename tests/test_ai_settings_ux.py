import ast
import os
import sys

APP_PATH = "case_documentation_app.py"

def test_placeholders_present():
    """
    Static analysis to ensure placeholders are PRESENT and correct for AI settings.
    """
    if not os.path.exists(APP_PATH):
        print(f"{APP_PATH} not found")
        sys.exit(1)

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Inputs we want to check and their expected placeholders
    target_placeholders = {
        "OpenAI API Key": "sk-...",
        "AI Base URL": ["https://api.openai.com/v1", "http://localhost:1234/v1"],
        "API Key (optional)": "sk-..."
    }

    # Tracking found placeholders.
    # For 'AI Base URL' which appears twice, we want to confirm BOTH are found.
    found_placeholders = {
        "OpenAI API Key": False,
        "API Key (optional)": False,
        "AI Base URL (Cloud)": False,
        "AI Base URL (Local)": False
    }

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for st.text_input(...) calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == "text_input":
                # Extract label
                label = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant): # python 3.8+
                        label = node.args[0].value
                    elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str): # older python
                        label = node.args[0].s

                if not label:
                    for kw in node.keywords:
                        if kw.arg == "label":
                            if isinstance(kw.value, ast.Constant):
                                label = kw.value.value
                            elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                                label = kw.value.s

                if label in target_placeholders:
                    # Extract placeholder value
                    placeholder_value = None
                    for kw in node.keywords:
                        if kw.arg == "placeholder":
                            if isinstance(kw.value, ast.Constant):
                                placeholder_value = kw.value.value
                            elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                                placeholder_value = kw.value.s

                    if label == "AI Base URL":
                        # We need to distinguish between the two occurrences
                        if placeholder_value == "https://api.openai.com/v1":
                            found_placeholders["AI Base URL (Cloud)"] = True
                        elif placeholder_value == "http://localhost:1234/v1":
                            found_placeholders["AI Base URL (Local)"] = True
                    else:
                        expected = target_placeholders[label]
                        if placeholder_value == expected:
                            found_placeholders[label] = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Check findings
    missing = [key for key, found in found_placeholders.items() if not found]

    if missing:
        print(f"FAIL: Missing or incorrect placeholders for: {missing}")
        sys.exit(1)
    else:
        print("SUCCESS: All target placeholders are present and correct.")

if __name__ == "__main__":
    test_placeholders_present()
