import { test, expect } from '@playwright/test';

test('Sanity check - App Loads', async ({ page }) => {
  // Just verify the test runner works and can navigate to the page
  await page.goto('/');
  // Basic assertion to ensure we are on the right page (assuming default Streamlit title or similar)
  // Since we don't know the exact content, checking the title is safer, or just checking page load.
  await expect(page).toHaveTitle(/Kiroshi/);
});
