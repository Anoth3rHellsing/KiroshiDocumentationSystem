import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  await page.goto('/');
  await page.waitForTimeout(2000);
  await expect(page.locator('.stApp')).toBeVisible();
});