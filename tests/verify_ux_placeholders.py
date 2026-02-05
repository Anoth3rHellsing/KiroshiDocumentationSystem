import ast
import sys

def verify_placeholders(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    required_fields = {
        "dell_issue_start_date": ["help", "placeholder"],
        "dell_command_updates_status": ["help", "placeholder"],
        "dell_power_options_setup": ["help", "placeholder"],
        "dell_optimizer_setup": ["help", "placeholder"],
        "dell_intel_ppm_installed": ["help", "placeholder"],
        "dell_cpu_speed_or_throttling": ["help", "placeholder"],
        "dell_gpu_usage_integrated": ["help", "placeholder"],
        "dell_gpu_usage_dedicated": ["help", "placeholder"],
        "dell_cpu_utilization": ["help", "placeholder"],
        "dell_benchmark_results": ["help", "placeholder"],
        "dell_gpu_driver_versions": ["help", "placeholder"],
        "dell_ultra_resolution_support": ["help", "placeholder"],
        "dell_reliability_monitor_results": ["help", "placeholder"],
        "dell_diagnostics_results": ["help", "placeholder"],
        "dell_windows_reimaged": ["help", "placeholder"],
        "clinic_name": ["help", "placeholder"],
        "clinic_contact_name": ["help", "placeholder"],
        "clinic_contact_phone": ["help", "placeholder"],
        "clinic_contact_email": ["help", "placeholder"],
        "clinic_address_line_1": ["help", "placeholder"],
        "clinic_address_line_2": ["help", "placeholder"],
        "clinic_city": ["help", "placeholder"],
        "clinic_state": ["help", "placeholder"],
        "clinic_postal_code": ["help", "placeholder"],
    }

    found_fields = {}

    class PlaceholderVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            if isinstance(node.func, ast.Name) and node.func.id in ("auto_text_input", "auto_text_area"):
                # Check arguments
                if len(node.args) >= 2:
                    arg_val = None
                    if isinstance(node.args[1], ast.Constant): # Python 3.8+
                         arg_val = node.args[1].value
                    elif isinstance(node.args[1], ast.Str): # Python < 3.8
                         arg_val = node.args[1].s

                    if arg_val and arg_val in required_fields:
                        if arg_val not in found_fields:
                            found_fields[arg_val] = set()
                        for keyword in node.keywords:
                            if keyword.arg in required_fields[arg_val]:
                                found_fields[arg_val].add(keyword.arg)
            self.generic_visit(node)

    PlaceholderVisitor().visit(tree)

    missing_attributes = []
    for field, requirements in required_fields.items():
        if field not in found_fields:
            missing_attributes.append(f"Field '{field}' not found in auto_text_input/area calls.")
        else:
            found = found_fields[field]
            for req in requirements:
                if req not in found:
                    missing_attributes.append(f"Field '{field}' missing attribute '{req}'.")

    if missing_attributes:
        print("Verification Failed:")
        for msg in missing_attributes:
            print(f"- {msg}")
        sys.exit(1)
    else:
        print("Verification Passed: All Dell Escalation fields have help and placeholder attributes.")

if __name__ == "__main__":
    verify_placeholders("case_documentation_app.py")
