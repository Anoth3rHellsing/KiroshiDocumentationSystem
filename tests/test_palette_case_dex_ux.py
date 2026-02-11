import ast
import os

def test_case_dex_input_ux():
    """
    Verify that the 'Case Dex' input field has the appropriate UX attributes.
    """
    file_path = "case_documentation_app.py"
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    target_node = None

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            # Check if it's a st.text_input call
            is_text_input = False
            if isinstance(node.func, ast.Attribute) and node.func.attr == 'text_input':
                is_text_input = True

            if is_text_input:
                # Check for label "Case ID"
                has_correct_label = False
                if node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "Case ID":
                    has_correct_label = True

                # Check for key="case_dex_id" (partially matching based on previous exploration)
                has_correct_key = False
                for keyword in node.keywords:
                    if keyword.arg == 'key':
                        # The key is likely a call to save_tab_key("case_dex_id")
                        if isinstance(keyword.value, ast.Call):
                            if keyword.value.args and isinstance(keyword.value.args[0], ast.Constant) and keyword.value.args[0].value == "case_dex_id":
                                has_correct_key = True

                if has_correct_label and has_correct_key:
                    target_node = node
                    break

    assert target_node is not None, "Could not find the Case Dex input field in the code."

    # Check for help and placeholder attributes
    help_value = None
    placeholder_value = None

    for keyword in target_node.keywords:
        if keyword.arg == 'help':
            if isinstance(keyword.value, ast.Constant):
                help_value = keyword.value.value
        if keyword.arg == 'placeholder':
            if isinstance(keyword.value, ast.Constant):
                placeholder_value = keyword.value.value

    # Assert that they are PRESENT and have correct values
    assert help_value == "Enter the Case ID to fetch data from the Case Dex system.", "Help tooltip is missing or incorrect!"
    assert placeholder_value == "e.g. CS-12345", "Placeholder is missing or incorrect!"
