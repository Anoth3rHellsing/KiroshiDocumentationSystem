import { test, expect } from '@playwright/test';

test('sanity check: app loads and title is correct', async ({ page }) => {
  // Navigate to the app (baseURL is set in config)
  await page.goto('/');

  // Wait for the title to be correct (Streamlit apps load 'Streamlit' first)
  // We expect "Kiroshi Documentation System" or similar based on README/Memory
  await expect(page).toHaveTitle(/Kiroshi/);
});
