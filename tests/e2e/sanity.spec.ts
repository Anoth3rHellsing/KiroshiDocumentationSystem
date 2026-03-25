import { test, expect } from '@playwright/test';

test('App load verification', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await expect(page.locator('text=Welcome to Kiroshi').first()).toBeVisible();
});