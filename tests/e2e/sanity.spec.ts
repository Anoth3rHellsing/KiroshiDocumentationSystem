import { test, expect } from '@playwright/test';

test('app loads and renders stApp', async ({ page }) => {
  await page.goto('http://127.0.0.1:8501');
  await page.waitForTimeout(2000);
  const stApp = page.locator('.stApp');
  await expect(stApp).toBeVisible();
});
