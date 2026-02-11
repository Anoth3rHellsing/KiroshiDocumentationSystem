
import { test, expect } from '@playwright/test';

test('sanity check', async ({ page }) => {
  // Simple check to verify the app loads
  await page.goto('/');
  // Streamlit apps usually have "Streamlit" in title or the app name
  // Just checking we didn't get a 404 or connection refused (which playwright handles)
  await expect(page).toHaveTitle(/Kiroshi/);
});
