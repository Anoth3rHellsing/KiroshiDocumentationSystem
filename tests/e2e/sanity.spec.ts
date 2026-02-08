
import { test, expect } from '@playwright/test';

test('Sanity check: Application loads', async ({ page }) => {
  await page.goto('/');

  // Wait for the main app container
  await page.waitForSelector('[data-testid="stAppViewContainer"]', { timeout: 30000 });

  // Check for the Dashboard tab specifically.
  // Streamlit tabs have role="tab" and the name is the label.
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible({ timeout: 30000 });

  // Verify "Tracked Cases" header is present on the Dashboard.
  // This might also appear in the tutorial text, so we should be careful.
  // But strictly speaking, if it's visible, the app loaded.
  // We can use first() to avoid strict mode if multiple exist.
  await expect(page.getByText('Tracked Cases', { exact: false }).first()).toBeVisible({ timeout: 30000 });
});
