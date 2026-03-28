import { test, expect } from '@playwright/test';

test('App load sanity check', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await expect(page.locator('.stApp')).toBeVisible({ timeout: 10000 });
});
