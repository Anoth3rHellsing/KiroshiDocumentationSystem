import { test, expect } from '@playwright/test';

test('App loads and renders basic structure', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await page.waitForTimeout(2000);
  const appContainer = page.locator('.stApp');
  await expect(appContainer).toBeVisible({ timeout: 10000 });
});
