import { test, expect } from '@playwright/test';

test('Application loads successfully', async ({ page }) => {
  await page.goto('/');
  const stApp = page.locator('.stApp');
  await expect(stApp).toBeVisible();
});
