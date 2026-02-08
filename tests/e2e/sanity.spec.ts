import { test, expect } from '@playwright/test';

test('App sanity check', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi/);
  // Wait for main container to ensure app loaded
  await expect(page.locator('.stApp')).toBeVisible();
});
