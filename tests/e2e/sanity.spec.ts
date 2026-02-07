import { test, expect } from '@playwright/test';

test('Sanity check: Application loads and shows Dashboard', async ({ page }) => {
  // Go to the home page (baseURL is configured in playwright.config.ts)
  await page.goto('/');

  // Streamlit apps can be slow to start, increase timeout if necessary
  // Wait for the app to be ready (look for main container or specific text)

  // Dashboard is the first tab
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible({ timeout: 60000 });

  await dashboardTab.click();

  // Verify some content on the Dashboard
  // "Tracked Cases" is a header in the dashboard
  await expect(page.getByText('Tracked Cases')).toBeVisible();
});
