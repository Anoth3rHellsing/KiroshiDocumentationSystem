import { test, expect } from '@playwright/test';

test('App load successfully', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.stApp')).toBeVisible();
});
