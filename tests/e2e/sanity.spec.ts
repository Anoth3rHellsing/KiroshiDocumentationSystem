import { test, expect } from '@playwright/test';

test('app loads successfully', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await expect(page.locator('.stApp')).toBeVisible();
});
