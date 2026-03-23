import { test, expect } from '@playwright/test';
test('sanity check', async ({ page }) => {
  await page.goto('http://localhost:8501');
  await expect(page).toHaveTitle(/Kiroshi/i);
});
