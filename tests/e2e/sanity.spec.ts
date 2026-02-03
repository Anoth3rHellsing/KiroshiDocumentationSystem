import { test, expect } from '@playwright/test';

test('sanity check - page loads and title is correct', async ({ page }) => {
  await page.goto('/');
  // Allow time for Streamlit to hydrate
  await expect(page).toHaveTitle(/Kiroshi|Streamlit/);
});
