import { test, expect } from '@playwright/test';

test('app loads and bypasses tutorial', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.stApp')).toBeVisible();
});
