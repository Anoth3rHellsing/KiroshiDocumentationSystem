import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  // Use a long timeout to allow the app to boot
  test.setTimeout(120_000);

  await page.goto('/', { timeout: 120_000, waitUntil: 'domcontentloaded' });

  // Verify basic structure loads
  await expect(page.locator('.stApp').first()).toBeVisible({ timeout: 60_000 });
});
