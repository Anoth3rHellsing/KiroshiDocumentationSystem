import { test, expect } from '@playwright/test';

test.describe('Sanity Check', () => {
  test('Application loads and shows title', async ({ page }) => {
    // Navigate to the app (baseURL is set in config)
    await page.goto('/');

    // Wait for Streamlit to render the main container
    // We look for the main app container or a specific element that indicates loaded state
    // "stApp" is the class on the root div
    await expect(page.locator('.stApp')).toBeVisible({ timeout: 30000 });

    // Verify title - Streamlit apps usually have the title in the title tag or an h1
    // Based on memory, there might be a "Dashboard" tab or header.
    // Let's check for the presence of the main tab list.
    await expect(page.getByRole('tablist')).toBeVisible();

    // Check if "Dashboard" tab is present
    await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
  });
});
