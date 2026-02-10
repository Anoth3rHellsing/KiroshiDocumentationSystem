import { test, expect } from '@playwright/test';

test('App loads successfully', async ({ page }) => {
  await page.goto('/');
  // Wait for the main container
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible({ timeout: 15000 });

  // Verify Dashboard tab exists
  await expect(page.getByRole('tab', { name: 'Dashboard' })).toBeVisible();
});
