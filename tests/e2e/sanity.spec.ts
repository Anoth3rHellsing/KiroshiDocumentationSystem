import { test, expect } from '@playwright/test';

test('Sanity check - app loads', async ({ page }) => {
  await page.goto('/');
  // Allow time for streamlit to load
  await expect(page).toHaveTitle(/Kiroshi/, { timeout: 30000 });
});
