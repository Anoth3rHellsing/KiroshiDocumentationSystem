import { test, expect } from '@playwright/test';
test('basic load', async ({ page }) => {
  await page.goto('http://127.0.0.1:8501');
  await expect(page).toHaveTitle(/Kiroshi/i);
});
