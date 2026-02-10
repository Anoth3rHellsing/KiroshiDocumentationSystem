import { test, expect } from '@playwright/test';

test('Sanity check - App Loads', async ({ page }) => {
  // Navigate to the app (baseURL is configured in playwright.config.ts)
  await page.goto('/');

  // Wait for the main app container to be visible
  // Streamlit apps typically have a data-testid="stAppViewContainer"
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 30000 });

  // Verify the Dashboard tab is present
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
