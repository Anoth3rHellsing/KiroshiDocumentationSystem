import ast
from pathlib import Path

def test_settings_inputs_have_placeholders_and_help():
    """
    Static analysis to ensure critical Settings inputs have helpful placeholders
    and tooltips to guide the user.
    """
    app_path = Path("case_documentation_app.py")
    if not app_path.exists():
        # Fallback if running from tests/
        app_path = Path("../case_documentation_app.py")

    tree = ast.parse(app_path.read_text(encoding="utf-8"))

    found_checks = {
        "attachments_folder_placeholder": False,
        "openai_api_key_placeholder": False,
        "ai_base_url_cloud_placeholder": False,
        "ai_base_url_local_placeholder": False,
        "local_api_key_help": False,
        "local_api_key_placeholder": False
    }

    class UXVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Check for st.text_input calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == "text_input":
                args = [arg.value for arg in node.args if isinstance(arg, ast.Constant)]
                label = args[0] if args else None

                # Check keyword arguments
                kwargs = {kw.arg: kw.value for kw in node.keywords}
                has_placeholder = "placeholder" in kwargs
                has_help = "help" in kwargs

                if label == "Attachments folder":
                    if has_placeholder:
                        found_checks["attachments_folder_placeholder"] = True

                elif label == "OpenAI API Key":
                    # Distinguish by context if possible, or just accept if found.
                    # Since the labels are identical in Cloud vs Local (optional), we check attributes.
                    # But wait, Cloud is "OpenAI API Key", Local is "API Key (optional)".
                    if has_placeholder:
                         found_checks["openai_api_key_placeholder"] = True

                elif label == "AI Base URL":
                    # We have two of these. We can't easily distinguish by label alone in simple AST
                    # unless we track parent nodes.
                    # For simplicity, we'll check if we find *at least* two occurrences with placeholders,
                    # or better yet, check the placeholder values if they exist.
                    if has_placeholder:
                        placeholder_node = kwargs["placeholder"]
                        if isinstance(placeholder_node, ast.Constant):
                            val = placeholder_node.value
                            if "api.openai.com" in val:
                                found_checks["ai_base_url_cloud_placeholder"] = True
                            elif "localhost" in val:
                                found_checks["ai_base_url_local_placeholder"] = True

                elif label == "API Key (optional)":
                    if has_help:
                        found_checks["local_api_key_help"] = True
                    if has_placeholder:
                        found_checks["local_api_key_placeholder"] = True

            self.generic_visit(node)

    UXVisitor().visit(tree)

    missing = [k for k, v in found_checks.items() if not v]
    assert not missing, f"Missing UX attributes for: {', '.join(missing)}"

if __name__ == "__main__":
    test_settings_inputs_have_placeholders_and_help()
