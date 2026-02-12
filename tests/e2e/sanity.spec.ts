import { test, expect } from '@playwright/test';

test('App sanity check - Title loads', async ({ page }) => {
  // Navigate to the app (baseURL is configured in playwright.config.ts)
  await page.goto('/');

  // Wait for the title to be correct
  // The app title is likely "Kiroshi Documentation System" or similar based on the code analysis
  // Using a regex to be flexible
  await expect(page).toHaveTitle(/Kiroshi/i);

  // Optional: Check for a key element to ensure rendering
  // Streamlit apps usually have a main container
  await expect(page.locator('.stApp')).toBeVisible();
});
