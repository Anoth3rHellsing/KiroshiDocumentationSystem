import re
import sys
from pathlib import Path

def verify_tooltips():
    app_path = Path("case_documentation_app.py")
    if not app_path.exists():
        print("case_documentation_app.py not found.")
        sys.exit(1)

    content = app_path.read_text(encoding="utf-8")

    # Regex to find buttons with onclick attributes that start with 'copy'
    # We are looking for: <button onclick="copy..." ... >
    # And we want to check if they have title=... and aria-label=...

    # This regex finds the entire opening tag of buttons calling a copy function
    # It handles multiline matching because the buttons are often defined across multiple lines in the f-strings
    button_pattern = re.compile(r'<button\s+[^>]*onclick=\\?["\']copy[^>]*>', re.IGNORECASE | re.DOTALL)

    matches = button_pattern.findall(content)

    missing_attributes = []

    for button_tag in matches:
        # Normalize whitespace for display
        display_tag = " ".join(button_tag.split())

        # Check if 'title' attribute is present
        if 'title=' not in button_tag:
            missing_attributes.append(f"Missing 'title': {display_tag}")

        # Check if 'aria-label' attribute is present
        if 'aria-label=' not in button_tag:
            missing_attributes.append(f"Missing 'aria-label': {display_tag}")

    if missing_attributes:
        print(f"Found {len(missing_attributes)} accessibility issues in copy buttons:")
        for issue in missing_attributes:
            print(f"- {issue}")
        sys.exit(1)

    print("All copy buttons have title and aria-label attributes!")
    sys.exit(0)

if __name__ == "__main__":
    verify_tooltips()
