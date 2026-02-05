import { test, expect } from '@playwright/test';

test('has title', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Kiroshi/);
});

test('loads dashboard', async ({ page }) => {
  await page.goto('/');

  // Wait for the main content to load
  // We can look for "Dashboard" tab or text.
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 30000 });
});
