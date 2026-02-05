import ast
import sys

def verify_placeholders_and_help():
    with open("case_documentation_app.py", "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Map field name to list of required attributes
    required_fields = {
        "dell_command_updates_status": ["help", "placeholder"],
        "dell_power_options_setup": ["help", "placeholder"],
        "dell_optimizer_setup": ["help", "placeholder"],
        "dell_intel_ppm_installed": ["help", "placeholder"],
        "dell_cpu_speed_or_throttling": ["help", "placeholder"],
        "dell_gpu_usage_integrated": ["placeholder"],
        "dell_gpu_usage_dedicated": ["placeholder"],
        "dell_cpu_utilization": ["placeholder"],
    }

    # Track which requirements are met
    # Structure: field_name -> set of found attributes
    found_attributes = {field: set() for field in required_fields}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "auto_text_input":
            # Check if this call is for one of our fields
            field_name = None
            # Inspect args
            if len(node.args) >= 2:
                arg1 = node.args[1]
                if isinstance(arg1, ast.Constant): # Python 3.8+
                     field_name = arg1.value
                elif isinstance(arg1, ast.Str): # Fallback
                     field_name = arg1.s

            if field_name in required_fields:
                for kw in node.keywords:
                    if kw.arg in ["help", "placeholder"]:
                        found_attributes[field_name].add(kw.arg)

    missing_errors = []
    for field, requirements in required_fields.items():
        found = found_attributes[field]
        for req in requirements:
            if req not in found:
                missing_errors.append(f"{field} is missing '{req}'")

    if missing_errors:
        print("❌ Verification failed:")
        for error in missing_errors:
            print(f"  - {error}")
        sys.exit(1)
    else:
        print("✅ All targeted fields have required help and placeholder text.")
        sys.exit(0)

if __name__ == "__main__":
    verify_placeholders_and_help()
