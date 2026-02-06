import { test, expect } from '@playwright/test';

test('App loads and Dashboard tab is visible', async ({ page }) => {
  // Base URL is set in playwright.config.ts (usually http://127.0.0.1:8501)
  await page.goto('/');

  // Wait for the Dashboard tab to be visible.
  // In Streamlit, tabs are often role="tab" with the name being the text.
  // We use a generous timeout because Streamlit startup can be slow in CI.
  const dashboardTab = page.getByRole('tab', { name: 'Dashboard' });

  await expect(dashboardTab).toBeVisible({ timeout: 60000 });
});
