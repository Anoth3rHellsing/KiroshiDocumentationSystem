import { test, expect } from '@playwright/test';

test('App load sanity check', async ({ page }) => {
    // Sanity check for Streamlit app
    await page.goto('/');

    // Wait for the Streamlit app container to be attached to the DOM
    await page.waitForSelector('.stApp', { timeout: 15000 });

    // Check if the app container is visible
    const appContainer = page.locator('.stApp');
    await expect(appContainer).toBeVisible();
});
