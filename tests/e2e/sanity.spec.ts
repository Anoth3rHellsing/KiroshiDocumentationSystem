import { test, expect } from '@playwright/test';

test('Sanity check - App loads', async ({ page }) => {
  await page.goto('/');
  // Streamlit app title often takes a moment to set from the default "Streamlit"
  await expect(page).toHaveTitle(/Kiroshi|Streamlit/, { timeout: 10000 });
});
