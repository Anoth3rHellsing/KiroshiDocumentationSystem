import { test, expect } from '@playwright/test';

test.describe('Sanity Check', () => {
  test('Application loads and dashboard is visible', async ({ page }) => {
    // Navigate to the app (baseURL is set in config)
    await page.goto('/');

    // Wait for the main app container to ensure it's loaded
    // Streamlit apps typically have a view container
    await expect(page.locator('.stApp')).toBeVisible({ timeout: 30000 });

    // Check for a specific tab or header to confirm content is rendering
    // Using loose matching for resiliency
    await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
  });
});
