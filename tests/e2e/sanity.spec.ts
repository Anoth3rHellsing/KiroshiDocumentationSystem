import { test, expect } from '@playwright/test';

test('sanity check - app loads', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await expect(page.locator('.stApp')).toBeVisible({ timeout: 15000 });
});