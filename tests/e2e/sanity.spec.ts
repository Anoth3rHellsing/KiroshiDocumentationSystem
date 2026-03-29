import { test, expect } from '@playwright/test';

test('App loads successfully and displays main UI', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.stApp')).toBeVisible();
});
