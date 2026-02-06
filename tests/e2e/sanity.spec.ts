import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the app to load (Streamlit usually puts the app in a div with class 'stApp')
  await expect(page.locator('.stApp')).toBeVisible({ timeout: 30000 });

  // Verify the Dashboard tab exists
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();

  // Verify basic title or header
  await expect(page).toHaveTitle(/Kiroshi/);
});
