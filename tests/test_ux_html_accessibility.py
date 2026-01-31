import re
import os
import pytest

APP_PATH = "case_documentation_app.py"

def test_copy_buttons_have_accessibility_attributes():
    """
    Ensure that HTML buttons injected via components.html have title and aria-label attributes.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern for Copy Title button
    # Expecting: <button onclick=\"copyTitle...
    copy_title_pattern = re.compile(r'<button\s+onclick=\\"copyTitle[^>]*>')
    matches = copy_title_pattern.findall(content)

    accessible_copy_title_pattern = re.compile(r'<button\s+onclick=\\"copyTitle[^>]*\s+title=\\"[^"]*\\"\s+aria-label=\\"[^"]*\\"[^>]*>')
    accessible_matches = accessible_copy_title_pattern.findall(content)

    assert len(matches) > 0, "No 'Copy title' buttons found to test"
    assert len(matches) == len(accessible_matches), \
        f"Found {len(matches)} 'Copy title' buttons, but only {len(accessible_matches)} have accessibility attributes."

    # Pattern for Copy Table button
    # Expecting: <button onclick=\"copyTable...
    copy_table_pattern = re.compile(r'<button\s+onclick=\\"copyTable[^>]*>')
    matches_table = copy_table_pattern.findall(content)

    accessible_copy_table_pattern = re.compile(r'<button\s+onclick=\\"copyTable[^>]*\s+title=\\"[^"]*\\"\s+aria-label=\\"[^"]*\\"[^>]*>')
    accessible_matches_table = accessible_copy_table_pattern.findall(content)

    assert len(matches_table) > 0, "No 'Copy table' buttons found to test"
    assert len(matches_table) == len(accessible_matches_table), \
        f"Found {len(matches_table)} 'Copy table' buttons, but only {len(accessible_matches_table)} have accessibility attributes."

def test_remote_buttons_have_accessibility_attributes():
    """
    Ensure remote session copy buttons have title and aria-label.
    """
    if not os.path.exists(APP_PATH):
        pytest.skip(f"{APP_PATH} not found")

    with open(APP_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern for copyRemotePayload buttons
    remote_btn_pattern = re.compile(r'<button\s+onclick=\\"copyRemotePayload[^>]*>')
    matches = remote_btn_pattern.findall(content)

    accessible_remote_btn_pattern = re.compile(r'<button\s+onclick=\\"copyRemotePayload[^>]*\s+title=\\"[^"]*\\"\s+aria-label=\\"[^"]*\\"[^>]*>')
    accessible_matches = accessible_remote_btn_pattern.findall(content)

    assert len(matches) > 0, "No remote copy buttons found to test"
    assert len(matches) == len(accessible_matches), \
        f"Found {len(matches)} remote copy buttons, but only {len(accessible_matches)} have accessibility attributes."
