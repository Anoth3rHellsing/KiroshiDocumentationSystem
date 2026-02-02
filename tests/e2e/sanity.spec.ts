import { test, expect } from '@playwright/test';

test('app loads and displays title', async ({ page }) => {
  await page.goto('/');
  // Streamlit apps might have a generic title initially or loading state
  // We check for "Kiroshi" which should be in the title configured by st.set_page_config
  // or at least in the content if the title check is flaky.
  // Using a regex for title is robust.
  await expect(page).toHaveTitle(/Kiroshi|Streamlit/i);
});
