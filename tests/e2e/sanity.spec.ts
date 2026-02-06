import { test, expect } from '@playwright/test';

test('app loads and dashboard is visible', async ({ page }) => {
  // Navigate to the app (baseURL is set in config to http://127.0.0.1:8501)
  await page.goto('/');

  // Wait for the Dashboard tab to be visible, indicating the app has initialized
  // and bypassed the tutorial (handled by global-setup).
  // Increased timeout to account for initial Streamlit boot time.
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 60000 });

  // Verify the dashboard title is present
  await expect(page.locator('div.dashboard-title').filter({ hasText: /^Dashboard$/ })).toBeVisible();
});
