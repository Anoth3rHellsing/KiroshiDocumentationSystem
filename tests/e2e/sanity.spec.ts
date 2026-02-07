import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  console.log('Navigating to home page...');
  await page.goto('/');

  // Wait for the app to load
  console.log('Waiting for title...');
  await expect(page).toHaveTitle(/Kiroshi/);

  // Check for dashboard tab
  console.log('Checking for Dashboard tab...');
  // Streamlit tabs are often buttons with role 'tab'
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();

  // Check for 'Tracked Cases' text which indicates the dashboard is rendered
  console.log('Checking for Tracked Cases...');
  await expect(page.getByText('Tracked Cases', { exact: true })).toBeVisible();
});
