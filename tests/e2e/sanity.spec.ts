
import { test, expect } from '@playwright/test';

test('App loads and title is correct', async ({ page }) => {
  // The base URL is configured in playwright.config.ts (defaulting to http://127.0.0.1:8501)
  await page.goto('/');

  // Streamlit app title often includes the page name or config title
  // Kiroshi sets it to "Kiroshi <VERSION>"
  await expect(page).toHaveTitle(/Kiroshi/);
});
