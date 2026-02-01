import { test, expect } from '@playwright/test';

test('Sanity check', async ({ page }) => {
  await page.goto('/');
  // Wait for title to eventually be correct, handling Streamlit loading state
  await expect(page).toHaveTitle(/Kiroshi/);
});
