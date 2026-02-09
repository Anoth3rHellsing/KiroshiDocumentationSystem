import { test, expect } from '@playwright/test';

test('App sanity check', async ({ page }) => {
  await page.goto('/');

  // Wait for the app container to ensure Streamlit loaded
  // Streamlit apps are rendered inside a container with class stApp or data-testid="stAppViewContainer"
  // We use a flexible selector to be robust
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 30000 });

  // Check for the Dashboard tab to verify content loaded
  // Using exact: true to avoid matching "Dashboard" in other contexts if any
  await expect(page.getByRole('tab', { name: 'Dashboard', exact: true })).toBeVisible();
});
