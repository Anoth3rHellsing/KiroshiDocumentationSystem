import { test, expect } from '@playwright/test';

test('sanity check: app loads and dashboard is visible', async ({ page }) => {
  // The base URL is configured in playwright.config.ts (defaulting to http://127.0.0.1:8501)
  await page.goto('/');

  // Wait for the main Streamlit container to load
  await page.waitForSelector('[data-testid="stAppViewContainer"]', { timeout: 30000 });

  // Verify the title is correct (based on config)
  await expect(page).toHaveTitle(/Kiroshi/);

  // Verify the 'Dashboard' tab is present.
  // Using getByRole with name option to avoid strict mode violations if multiple elements have text 'Dashboard'
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });
  await expect(dashboardTab).toBeVisible();
});
