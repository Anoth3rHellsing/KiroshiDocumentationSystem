import { test, expect } from '@playwright/test';

test('basic test', async ({ page }) => {
  await page.goto('http://127.0.0.1:8501');
  await expect(page.locator('.stApp')).toBeVisible();
});
