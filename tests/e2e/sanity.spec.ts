import { test, expect } from '@playwright/test';

test('App loads correctly', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('text=Welcome to Kiroshi').first()).toBeVisible();
});
