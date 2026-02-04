import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  await page.goto('/');

  // Expect a title "to contain" a substring.
  await expect(page).toHaveTitle(/Kiroshi/);

  // Wait for the Dashboard tab to ensure app loaded
  // Note: Streamlit tabs might be tricky, but role 'tab' usually works.
  // Using a timeout to allow for Streamlit startup/loading
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 30000 });
});
