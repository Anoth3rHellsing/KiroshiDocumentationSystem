import { test, expect } from '@playwright/test';

test('App loads and title is correct', async ({ page }) => {
  await page.goto('/');
  // Streamlit title might vary, but "Kiroshi" should be in it.
  // Using a loose check or checking for the app container.
  await expect(page).toHaveTitle(/Kiroshi/);
  await expect(page.getByTestId('stAppViewContainer')).toBeVisible();
});
