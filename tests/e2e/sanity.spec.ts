import { test, expect } from '@playwright/test';

test('app load verification', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await page.waitForTimeout(2000);

  // The first element matching the compound condition
  const welcome = page.locator('text=Welcome to Kiroshi').first();
  const dashboard = page.locator('text=The Dashboard Command Center').first();

  // Checking that either one is eventually visible
  await expect(welcome.or(dashboard).first()).toBeVisible({ timeout: 10000 });
});
