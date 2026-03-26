import { test, expect } from '@playwright/test';

test('app loads and displays welcome message', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await page.waitForTimeout(2000);
  await expect(page.locator('text=Welcome to Kiroshi').first()).toBeVisible({ timeout: 15000 });
});
