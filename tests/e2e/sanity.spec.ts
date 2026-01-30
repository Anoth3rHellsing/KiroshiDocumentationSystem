import { test, expect } from '@playwright/test';

test('sanity check - app loads', async ({ page }) => {
  console.log('Navigating to /...');
  await page.goto('/');

  console.log('Waiting for "Dashboard" text...');
  // Streamlit apps can be slow to load the first time
  await expect(page.getByText('Dashboard', { exact: false }).first()).toBeVisible({ timeout: 30000 });

  console.log('App loaded successfully');
});
