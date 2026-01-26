
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_buttons_have_tooltips():
    """
    Static analysis to ensure critical buttons have a 'help' tooltip defined.
    """
    if not os.path.exists(APP_PATH):
        # Fallback if running from tests/
        if os.path.exists(f"../{APP_PATH}"):
            path_to_read = f"../{APP_PATH}"
        else:
            pytest.skip(f"{APP_PATH} not found")
    else:
        path_to_read = APP_PATH

    with open(path_to_read, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Buttons we want to verify
    target_buttons = {
        "Save and track",
        "Close case & stop tracking",
        "Save",
        "Load"
    }

    # Store whether we found *at least one* instance of the button with a tooltip
    found_buttons = {btn: False for btn in target_buttons}

    class ButtonVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for st.button(...) calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == "button":
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

                if label in target_buttons:
                    has_help = any(kw.arg == "help" for kw in node.keywords)
                    if has_help:
                        found_buttons[label] = True

            self.generic_visit(node)

    ButtonVisitor().visit(tree)

    # Check findings
    missing_tooltips = [btn for btn, found in found_buttons.items() if not found]

    assert not missing_tooltips, f"The following buttons are missing tooltips in at least one instance: {missing_tooltips}"

def test_ai_settings_ux_compliance():
    """
    Verifies that AI settings inputs have required UX attributes (help/placeholder).
    """
    if not os.path.exists(APP_PATH):
         # Try parent dir if running from tests/
         if os.path.exists(f"../{APP_PATH}"):
             path_to_read = f"../{APP_PATH}"
         else:
             pytest.skip(f"{APP_PATH} not found")
    else:
         path_to_read = APP_PATH

    with open(path_to_read, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    target_func_name = "_render_settings_ai_tab"
    target_func = None

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == target_func_name:
            target_func = node
            break

    assert target_func is not None, f"Function {target_func_name} not found"

    def get_arg_value(call_node, arg_name):
        for keyword in call_node.keywords:
            if keyword.arg == arg_name:
                if isinstance(keyword.value, ast.Constant):
                    return keyword.value.value
                if hasattr(ast, "Str") and isinstance(keyword.value, ast.Str):
                    return keyword.value.s
        return None

    text_inputs = []

    for node in ast.walk(target_func):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "text_input":
                label = None
                if node.args:
                    if isinstance(node.args[0], ast.Constant):
                        label = node.args[0].value
                    elif hasattr(ast, "Str") and isinstance(node.args[0], ast.Str):
                        label = node.args[0].s

                if label:
                    text_inputs.append({
                        "label": label,
                        "help": get_arg_value(node, "help"),
                        "placeholder": get_arg_value(node, "placeholder")
                    })

    errors = []

    # Analyze findings
    ai_base_urls = [i for i in text_inputs if i["label"] == "AI Base URL"]
    openai_keys = [i for i in text_inputs if i["label"] == "OpenAI API Key"]
    optional_keys = [i for i in text_inputs if "API Key (optional)" in i["label"]]

    # Check Cloud API Key
    for inp in openai_keys:
        if not inp.get("placeholder"):
            errors.append(f"Missing placeholder for '{inp['label']}'")
        elif not inp["placeholder"].startswith("sk-"):
             errors.append(f"Placeholder for '{inp['label']}' should start with 'sk-', found '{inp['placeholder']}'")

    # Check AI Base URLs
    if len(ai_base_urls) >= 1:
        cloud_url = ai_base_urls[0]
        if not cloud_url.get("placeholder"):
            errors.append("Missing placeholder for Cloud 'AI Base URL'")
        elif "https://" not in cloud_url["placeholder"]:
            errors.append("Cloud 'AI Base URL' placeholder should contain 'https://'")

    if len(ai_base_urls) >= 2:
        local_url = ai_base_urls[1]
        if not local_url.get("placeholder"):
             errors.append("Missing placeholder for Local 'AI Base URL'")
        elif "http://" not in local_url["placeholder"]:
             errors.append("Local 'AI Base URL' placeholder should contain 'http://'")

    # Check Optional API Key
    for inp in optional_keys:
        if not inp.get("help"):
             errors.append(f"Missing help tooltip for '{inp['label']}'")
        if not inp.get("placeholder"):
             errors.append(f"Missing placeholder for '{inp['label']}'")

    if errors:
        pytest.fail("\n".join(errors))

if __name__ == "__main__":
    try:
        test_buttons_have_tooltips()
        print("Buttons test passed!")
        test_ai_settings_ux_compliance()
        print("AI Settings UX test passed!")
    except AssertionError as e:
        print(f"Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        exit(1)
