import { test, expect } from '@playwright/test';

test('App loads and Dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for the app to load (Streamlit's main container)
  await page.waitForSelector('div[class*="stApp"]', { timeout: 30000 });

  // Verify Dashboard tab exists
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible({ timeout: 30000 });
});
