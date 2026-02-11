import { test, expect } from '@playwright/test';

test('Sanity check - App loads', async ({ page }) => {
  // Go to the app URL
  await page.goto('/');

  // Wait for the app to load (look for the main container or specific text)
  // Streamlit apps usually have a main container with class 'stApp'
  await expect(page.locator('.stApp')).toBeVisible({ timeout: 30000 });

  // Check for the title (based on case_documentation_app.py render_dashboard)
  // It renders "<div class='dashboard-title'>Dashboard</div>"
  await expect(page.locator('.dashboard-title')).toHaveText('Dashboard');
});
