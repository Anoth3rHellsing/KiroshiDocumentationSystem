
import ast
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_dell_inputs_have_placeholders_and_help():
    """
    Static analysis to ensure Dell escalation inputs have 'placeholder' and 'help' defined.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read())

    # Fields we want to verify
    target_fields = {
        "dell_issue_start_date",
        "dell_command_updates_status",
        "dell_power_options_setup",
        "dell_optimizer_setup",
        "dell_intel_ppm_installed",
        "dell_cpu_speed_or_throttling",
        "dell_gpu_usage_integrated",
        "dell_gpu_usage_dedicated",
        "dell_cpu_utilization",
        "dell_benchmark_results",
        "dell_gpu_driver_versions",
        "dell_ultra_resolution_support",
        "dell_reliability_monitor_results",
        "dell_diagnostics_results",
        "dell_windows_reimaged"
    }

    # Tracking findings
    findings = {field: {"placeholder": False, "help": False} for field in target_fields}

    class InputVisitor(ast.NodeVisitor):
        def visit_Call(self, node):
            # Look for auto_text_input(...) or auto_text_area(...) calls
            if isinstance(node.func, ast.Name) and node.func.id in ("auto_text_input", "auto_text_area"):
                # The second argument is usually the field name
                field_name = None
                if len(node.args) >= 2:
                    arg_val = node.args[1]
                    if isinstance(arg_val, ast.Constant):
                        field_name = arg_val.value
                    elif hasattr(ast, "Str") and isinstance(arg_val, ast.Str):
                        field_name = arg_val.s

                # Check kwargs if field not in args (unlikely given usage, but safe)
                if not field_name:
                    for kw in node.keywords:
                        if kw.arg == "field":
                            if isinstance(kw.value, ast.Constant):
                                field_name = kw.value.value
                            elif hasattr(ast, "Str") and isinstance(kw.value, ast.Str):
                                field_name = kw.value.s

                if field_name in target_fields:
                    has_placeholder = any(kw.arg == "placeholder" for kw in node.keywords)
                    has_help = any(kw.arg == "help" for kw in node.keywords)

                    if has_placeholder:
                        findings[field_name]["placeholder"] = True
                    if has_help:
                        findings[field_name]["help"] = True

            self.generic_visit(node)

    InputVisitor().visit(tree)

    # Check findings
    failures = []
    for field, checks in findings.items():
        missing = []
        if not checks["placeholder"]:
            missing.append("placeholder")
        if not checks["help"]:
            missing.append("help")

        if missing:
            failures.append(f"{field} is missing: {', '.join(missing)}")

    assert not failures, "The following Dell escalation fields are missing UX attributes:\n" + "\n".join(failures)

if __name__ == "__main__":
    try:
        test_dell_inputs_have_placeholders_and_help()
        print("All target inputs have placeholders and help text!")
    except AssertionError as e:
        print(f"Test failed:\n{e}")
    except Exception as e:
        print(f"An error occurred: {e}")
