import { test, expect } from '@playwright/test';

test('app loads and shows Dashboard', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('text=Welcome to Kiroshi').first()).toBeVisible({ timeout: 10000 });
});
