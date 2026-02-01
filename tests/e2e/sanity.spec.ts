import { test, expect } from '@playwright/test';

test('Sanity check - App loads', async ({ page }) => {
  // Access the base URL defined in playwright.config.ts
  await page.goto('/');

  // Basic assertion to ensure the app is serving content
  // Streamlit apps usually have "Streamlit" in the title by default, or the configured title
  await expect(page).toHaveTitle(/Kiroshi|Streamlit/i);
});
