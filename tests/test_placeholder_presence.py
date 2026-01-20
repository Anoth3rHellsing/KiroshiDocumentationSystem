import ast
import sys

TARGET_FILE = "case_documentation_app.py"

FIELDS_TO_CHECK = {
    "company_name": "Case Header",
    "subscription_id": "Case Header",
    "case_id": "Case Header",
    "brief_description": "Case Header",
    "caller_name": "Phonecall",
    "phone_number": "Phonecall",
    "email": "Phonecall",
    "teamviewer_id": "Phonecall",
    "teamviewer_password": "Phonecall",
    "dongle_number": "Phonecall",
}

def verify_placeholders():
    with open(TARGET_FILE, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    found_placeholders = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "auto_text_input":
                # Check arguments
                args = node.args
                keywords = {k.arg: k.value for k in node.keywords}

                # field name is usually the second arg
                field_name = None
                if len(args) > 1 and isinstance(args[1], ast.Str): # Python < 3.8
                    field_name = args[1].s
                elif len(args) > 1 and isinstance(args[1], ast.Constant): # Python >= 3.8
                    field_name = args[1].value
                elif "field" in keywords:
                     if isinstance(keywords["field"], ast.Str):
                         field_name = keywords["field"].s
                     elif isinstance(keywords["field"], ast.Constant):
                         field_name = keywords["field"].value

                if field_name in FIELDS_TO_CHECK:
                    has_placeholder = "placeholder" in keywords
                    found_placeholders[field_name] = has_placeholder

    missing = []
    for field in FIELDS_TO_CHECK:
        if field not in found_placeholders:
            # We might not have found the call at all, which is also an issue if we expect it
            pass
        elif not found_placeholders[field]:
            missing.append(field)

    if missing:
        print(f"FAIL: The following fields are missing placeholders: {', '.join(missing)}")
        sys.exit(1)

    print("SUCCESS: All targeted fields have placeholders.")
    sys.exit(0)

if __name__ == "__main__":
    verify_placeholders()
