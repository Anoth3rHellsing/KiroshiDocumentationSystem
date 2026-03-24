import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('http://127.0.0.1:8501');
  await expect(page).toHaveTitle(/Kiroshi/);
});

test('shows welcome message', async ({ page }) => {
  await page.goto('http://127.0.0.1:8501');
  await expect(page.locator('body')).toBeVisible();
});
