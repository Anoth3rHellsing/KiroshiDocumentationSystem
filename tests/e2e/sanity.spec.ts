import { test, expect } from '@playwright/test';

test('sanity check: app loads and title is correct', async ({ page }) => {
  // Navigate to the app
  await page.goto('/');

  // Wait for the app to finish loading (Streamlit specific)
  // [data-testid="stAppViewContainer"] is usually present
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 30000 });

  // Verify title
  await expect(page).toHaveTitle(/Kiroshi/);

  // Verify that the tutorial is skipped and we see the main interface
  // We can look for "Add Case" button or "Dashboard" tab
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
