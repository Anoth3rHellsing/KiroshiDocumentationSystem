from playwright.sync_api import sync_playwright
import time

def verify_placeholders():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:8501")

        # Wait for app to load
        page.wait_for_selector("div.stApp", state="attached")

        # Give it some time to fully render
        time.sleep(5)

        # Look for the "+ New Case" tab and click it
        # Streamlit tabs are usually buttons with role="tab"
        new_case_tab = page.get_by_role("tab", name="+ New Case")
        if new_case_tab.count() > 0:
            new_case_tab.click()
            time.sleep(2)

            # Click "Add Case" button
            add_case_btn = page.get_by_role("button", name="Add Case")
            if add_case_btn.count() > 0:
                add_case_btn.click()
                time.sleep(5) # Wait for rerun

        # Now we should have a case tab open (e.g. "Case: ...")
        # We need to find the inputs.
        # Streamlit inputs usually have aria-label corresponding to the label.

        # Check 'Company name'
        company_input = page.get_by_label("Company name")
        if company_input.count() > 0:
            placeholder = company_input.get_attribute("placeholder")
            print(f"Company name placeholder: {placeholder}")
        else:
            print("Company name input not found")

        # Screenshot
        page.screenshot(path="verification/placeholders.png")
        browser.close()

if __name__ == "__main__":
    verify_placeholders()
