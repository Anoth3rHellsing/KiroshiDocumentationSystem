import { test, expect } from '@playwright/test';

test('application loads successfully', async ({ page }) => {
  await page.goto('/');

  // Wait for the main app container
  await page.waitForSelector('[data-testid="stAppViewContainer"]');

  // Verify the page title
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for the Dashboard tab using accessible role
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
