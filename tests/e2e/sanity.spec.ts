import { test, expect } from '@playwright/test';

test('app load verification', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('text=Welcome to Kiroshi').first()).toBeVisible({ timeout: 15000 });
});
