import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  await page.goto('/');
  // Wait for the main app container to appear (generic selector for Streamlit)
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 15000 });
});
