import { test, expect } from '@playwright/test';

test('App should load', async ({ page }) => {
  await page.goto('http://localhost:8501');
  const appElement = page.locator('.stApp');
  await expect(appElement).toBeVisible({ timeout: 15000 });
});
