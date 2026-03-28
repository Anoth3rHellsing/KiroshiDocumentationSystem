import { test, expect } from '@playwright/test';

test('App loads successfully and displays the main app container', async ({ page }) => {
  await page.goto('/');
  await page.waitForLoadState('networkidle');
  const appContainer = page.locator('.stApp');
  await expect(appContainer).toBeVisible({ timeout: 15000 });
});
