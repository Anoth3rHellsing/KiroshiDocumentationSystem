
import { test, expect } from '@playwright/test';

test('app loads and title is correct', async ({ page }) => {
  // The base URL is configured in playwright.config.ts (defaulting to http://127.0.0.1:8501)
  await page.goto('/');

  // Wait for the app to load
  await expect(page).toHaveTitle(/Kiroshi/);

  // Basic check for some content to ensure it's not just a blank page or error
  // Streamlit apps usually have a 'stApp' class
  await expect(page.locator('.stApp')).toBeVisible();
});
