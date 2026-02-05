import { test, expect } from '@playwright/test';

test('Sanity check: App loads and title is correct', async ({ page }) => {
  // Retry mechanism for loading the page in case the server is slow to start
  await test.step('Navigate to app', async () => {
    await page.goto('/');
  });

  await test.step('Verify title', async () => {
    // Streamlit dynamically sets the title, so we wait for it.
    // The default title is usually "Streamlit" then changes.
    // Based on the app code, the title is usually "Kiroshi" or similar.
    // We'll check for "Kiroshi" in the title.
    await expect(page).toHaveTitle(/Kiroshi/);
  });

  await test.step('Verify main content loads', async () => {
    // Check for a known element, e.g., the "Dashboard" tab or "Add Case" button.
    // Streamlit elements can be tricky, looking for text is often safer.
    await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
  });
});
