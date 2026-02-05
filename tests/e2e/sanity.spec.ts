import { test, expect } from '@playwright/test';

test.describe('Kiroshi App Sanity Check', () => {
  test('should load the dashboard and verify key tabs', async ({ page }) => {
    // Navigate to the app (baseURL is set in config)
    await page.goto('/');

    // Wait for the app to be ready (look for data-test-script-state='done' or main content)
    // Streamlit apps can be slow to initial render
    await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 60000 });

    // Verify main tabs are present
    await expect(page.getByRole('tab', { name: 'Sprint' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Saved Cases' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Settings' })).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Report' })).toBeVisible();

    // Verify Dashboard title is rendered
    // Use .first() or a more specific locator because 'dashboard-title' class is reused
    await expect(page.locator('div.dashboard-title').filter({ hasText: /^Dashboard$/ })).toBeVisible();
  });
});
