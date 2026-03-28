import { test, expect } from '@playwright/test';

test('App loads sanity check', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.stApp')).toBeVisible({ timeout: 10000 });
});
