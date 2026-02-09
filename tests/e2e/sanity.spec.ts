import { test, expect } from '@playwright/test';

test('App loads and Dashboard is visible', async ({ page }) => {
  await page.goto('/');

  // Wait for Streamlit app container
  await page.waitForSelector('[data-testid="stAppViewContainer"]', { state: 'visible', timeout: 30000 });

  // Check for Dashboard tab
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible();
});
