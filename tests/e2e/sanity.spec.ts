import { test, expect } from '@playwright/test';

test('app loads and displays title', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Kiroshi/);
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
