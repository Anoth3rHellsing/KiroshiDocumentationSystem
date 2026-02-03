import { test, expect } from '@playwright/test';

test('sanity check: app loads and title is correct', async ({ page }) => {
  await page.goto('/');
  // Streamlit apps usually have the title "Streamlit" initially or the configured page title.
  // We check for "Kiroshi" which is in the app title.
  await expect(page).toHaveTitle(/Kiroshi/);
});
