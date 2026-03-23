import { test, expect } from '@playwright/test';

test.describe('App Sanity Checks', () => {
  test('App loads successfully and shows Saved Cases tab', async ({ page }) => {
    // Navigate to the base URL (Streamlit app)
    await page.goto('/');

    // Check if the page has loaded successfully by asserting on a key element
    // We expect the 'Saved Cases' tab to be visible.
    const savedCasesTab = page.getByRole('tab', { name: 'Saved Cases' }).first();
    await expect(savedCasesTab).toBeVisible({ timeout: 60000 });
  });
});
