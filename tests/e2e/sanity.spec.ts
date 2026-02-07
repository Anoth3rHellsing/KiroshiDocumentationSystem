import { test, expect } from '@playwright/test';

test.describe('Kiroshi Sanity Checks', () => {
  test('Application loads and Dashboard is visible', async ({ page }) => {
    // Navigate to the app
    await page.goto('/');

    // Expect the title to contain "Kiroshi"
    await expect(page).toHaveTitle(/Kiroshi/);

    // Check for critical tabs
    await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 30000 });
    await expect(page.getByRole('tab', { name: 'Saved Cases' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Settings' })).toBeVisible();

    // Check for "Tracked Cases" header which should be on the dashboard
    await expect(page.getByRole('heading', { name: 'Tracked Cases' })).toBeVisible();
  });
});
