import { test, expect } from '@playwright/test';

test('app loads and shows dashboard', async ({ page }) => {
  await page.goto('http://localhost:8501');

  // Just wait for any text to appear to ensure app is running
  await expect(page.locator('.stApp')).toBeVisible({ timeout: 15000 });
});
