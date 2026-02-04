
import { test, expect } from '@playwright/test';

test('Sanity check: App loads', async ({ page }) => {
  await page.goto('/');
  // Wait for the app to be ready (Streamlit often takes a moment)
  // We can verify the title or look for a specific element.
  // Using a generic title expectation or waiting for a known element.

  // Streamlit apps usually have "Streamlit" in title initially, then update.
  // We expect something like "Kiroshi" or similar if set_page_config is used,
  // or just that the main container is present.

  await expect(page).toHaveTitle(/Kiroshi/i);

  // Check for the main block container
  await expect(page.locator('.block-container')).toBeVisible({ timeout: 30000 });
});
