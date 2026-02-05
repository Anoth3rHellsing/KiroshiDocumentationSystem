import { test, expect } from '@playwright/test';

test('sanity check: page loads', async ({ page }) => {
  await page.goto('/');
  // Streamlit apps can be slow to initial load, but expect will retry
  await expect(page).toHaveTitle(/Kiroshi/);
});
