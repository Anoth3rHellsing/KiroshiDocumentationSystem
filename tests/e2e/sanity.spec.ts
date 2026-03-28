import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await page.waitForTimeout(2000);
  const stApp = page.locator('.stApp');
  await expect(stApp).toBeVisible({ timeout: 15000 });
});
