import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.stApp')).toBeVisible({ timeout: 60_000 });
});
