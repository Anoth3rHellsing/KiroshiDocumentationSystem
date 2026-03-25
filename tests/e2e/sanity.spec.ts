import { test, expect } from '@playwright/test';

test('App should load', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('text=Welcome to Kiroshi').first()).toBeVisible();
});
