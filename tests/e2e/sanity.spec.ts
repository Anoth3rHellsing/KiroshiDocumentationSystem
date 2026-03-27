import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  // Navigate to the app
  await page.goto('/');

  // Verify app load by checking for the main container
  await expect(page.locator('.stApp')).toBeVisible({ timeout: 60000 });

  // Wait for the app to become interactive
  await page.waitForTimeout(2000);
});
