import { test, expect } from '@playwright/test';

test('App loads and Dashboard is visible', async ({ page }) => {
  // Go to the base URL (Streamlit app)
  await page.goto('/');

  // Wait for the "Dashboard" tab to be visible.
  // This implicitly waits for the app to load and render the tabs.
  // Increasing timeout just in case first load is slow.
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 45000 });
});
