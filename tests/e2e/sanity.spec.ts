import { test, expect } from '@playwright/test';

test('App sanity check', async ({ page }) => {
  // Go to the base URL configured in playwright.config.ts
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Kiroshi/);

  // Verify the app container loads
  await expect(page.locator('.stApp')).toBeVisible();
});
