import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  await page.goto('/');
  // Streamlit app title usually contains "Kiroshi"
  await expect(page).toHaveTitle(/Kiroshi/);
});
