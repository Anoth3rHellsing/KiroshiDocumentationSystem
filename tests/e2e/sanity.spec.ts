import { test, expect } from '@playwright/test';

test('basic test', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await expect(page.locator('text=Welcome to Kiroshi').first()).toBeVisible({ timeout: 10000 });
});
