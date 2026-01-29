import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  await page.goto('/');
  // Basic check to ensure the app is loading
  // We look for the main container or title
  await expect(page).toHaveTitle(/Kiroshi/);
});
