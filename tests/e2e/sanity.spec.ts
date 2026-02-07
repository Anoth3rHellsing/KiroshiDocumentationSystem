import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // Wait for the app to load
  await page.goto('/');

  // Wait for the main container
  // Increased timeout because Streamlit can be slow to start
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 60000 });

  // Check for Dashboard tab
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();

  // Verify main content is loaded
  await expect(page.getByText('Tracked Cases')).toBeVisible();
});
