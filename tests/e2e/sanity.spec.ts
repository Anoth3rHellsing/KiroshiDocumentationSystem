import { test, expect } from '@playwright/test';

test.describe('Sanity Check', () => {
  test('Application loads successfully', async ({ page }) => {
    // Navigate to the local application using the environment-injected base URL
    // If none provided, fallback to the typical local port
    const baseURL = process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:8501';

    await page.goto(baseURL);

    // Wait for the Streamlit health endpoint (or wait for the main app container)
    // The main app container is denoted by .stApp
    const appContainer = page.locator('.stApp');

    // Validate that the app container is visible, meaning the app loaded.
    await expect(appContainer).toBeVisible({ timeout: 15000 });
  });
});
