import ast
import sys

def check_placeholders(filename):
    with open(filename, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    fields_to_check = {
        "company_name": "Company Name",
        "subscription_id": "Subscription ID",
        "case_id": "Case ID",
        "brief_description": "Brief Description",
        "caller_name": "Caller Name",
        "phone_number": "Phone Number",
        "email": "Email",
        "teamviewer_id": "TeamViewer ID",
        "teamviewer_password": "TeamViewer Password",
        "dongle_number": "Dongle Number",
    }

    missing_placeholders = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "auto_text_input":
                # Check arguments
                args = node.args
                keywords = {k.arg: k.value for k in node.keywords}

                # field name is usually the second positional argument
                field_name = None
                if len(args) >= 2:
                    if isinstance(args[1], ast.Constant): # Python 3.8+
                        field_name = args[1].value
                    elif isinstance(args[1], ast.Str): # Older Python
                        field_name = args[1].s

                if field_name in fields_to_check:
                    if "placeholder" not in keywords:
                        missing_placeholders.append(field_name)

    if missing_placeholders:
        print("Missing placeholders for fields:")
        for field in missing_placeholders:
            print(f"- {field}")
        sys.exit(1)
    else:
        print("All specified fields have placeholders.")
        sys.exit(0)

if __name__ == "__main__":
    check_placeholders("case_documentation_app.py")
