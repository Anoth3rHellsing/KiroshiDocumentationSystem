import { test, expect } from '@playwright/test';

test('App load verification', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('text=Dashboard').first()).toBeVisible({ timeout: 15000 });
});
