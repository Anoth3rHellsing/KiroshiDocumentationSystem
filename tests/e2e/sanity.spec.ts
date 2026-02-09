import { test, expect } from '@playwright/test';

test('App sanity check', async ({ page }) => {
  await page.goto('/');

  // Wait for the main app container to be visible
  // Streamlit apps typically have a div with data-testid="stAppViewContainer"
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 30000 });

  // Verify the 'Dashboard' tab is present, which confirms the app loaded the tabs correctly
  // Using a loose match to be robust against slight changes
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
