import { test, expect } from '@playwright/test';

test('App sanity check', async ({ page }) => {
  // Go to the app
  await page.goto('/');

  // Wait for the app to load.
  // As learned: Playwright selectors in `tests/e2e/sanity.spec.ts` should check for `page.locator('.stApp')` to verify app load.
  await expect(page.locator('.stApp')).toBeVisible({ timeout: 60000 });
});
