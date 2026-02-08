import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  console.log('Navigating to app root...');
  await page.goto('/');

  console.log('Waiting for stAppViewContainer...');
  // Wait for the main app container to ensure Streamlit has initialized
  await page.waitForSelector('[data-testid="stAppViewContainer"]', { timeout: 60000 });

  console.log('Checking for Dashboard tab...');
  // Check for Dashboard tab using strict locator to avoid ambiguity
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible({ timeout: 30000 });
});
