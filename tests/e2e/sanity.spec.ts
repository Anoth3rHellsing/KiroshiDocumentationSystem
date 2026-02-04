import { test, expect } from '@playwright/test';

test('sanity check: app loads and title is correct', async ({ page }) => {
  // Navigate to the app
  await page.goto('/');

  // Wait for the app to load (title might take a moment to set by Streamlit)
  await expect(page).toHaveTitle(/Kiroshi/i);

  // Check for a key element to ensure UI is rendering
  // The app usually has a "Add Case" button or tabs
  // We can check for the main header or similar
  // Based on the code, "Kiroshi Control Tower" is for cloud client,
  // "Kiroshi Documentation System" is likely the main app title in README/Usage.
  // But let's look for something robust.
  // The app uses st.tabs(["Dashboard", "Sprint", ...])
  // Let's look for "Dashboard" tab.

  // Use getByRole for tab to avoid ambiguity
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 30000 });
});
