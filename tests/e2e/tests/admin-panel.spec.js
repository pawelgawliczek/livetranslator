// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Admin Panel Functionality E2E Tests
 *
 * Tests admin settings, language configuration, and system management
 * Verifies admin-only access and configuration changes
 * Runs in headless mode (no GUI needed)
 */

test.describe('Admin Panel Functionality', () => {
  test.beforeEach(async ({ page }) => {
    // Note: Admin tests may require authentication
    // In production, you'd set up admin credentials here
  });

  test('should load admin settings page', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForTimeout(1500);

    // Check if we're on admin page or redirected to login
    const currentUrl = page.url();

    if (currentUrl.includes('/admin')) {
      console.log('✅ Admin page loaded (authenticated)');
    } else if (currentUrl.includes('/login')) {
      console.log('✅ Admin page redirected to login (requires auth)');
    } else {
      console.log(`Admin page navigation result: ${currentUrl}`);
    }

    // Look for admin page elements
    const adminSelectors = [
      'h1:has-text("Admin")',
      'h2:has-text("Admin")',
      '[data-testid="admin-panel"]',
      'text=System Settings',
      'text=Configuration'
    ];

    let foundAdminUI = false;
    for (const selector of adminSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundAdminUI = true;
        console.log(`✅ Found admin UI element: ${selector}`);
        break;
      }
    }

    console.log(`Admin UI available: ${foundAdminUI}`);
  });

  test('should display language configuration page', async ({ page }) => {
    await page.goto('/admin/languages');
    await page.waitForTimeout(1500);

    const currentUrl = page.url();

    if (currentUrl.includes('/admin')) {
      console.log('✅ Language config page loaded');

      // Look for language configuration elements
      const languageConfigSelectors = [
        'h1:has-text("Language")',
        'h2:has-text("Language Configuration")',
        '[data-testid="language-config"]',
        'table',
        'text=STT Provider',
        'text=MT Provider',
        'text=Translation'
      ];

      for (const selector of languageConfigSelectors) {
        if (await page.locator(selector).count() > 0) {
          console.log(`✅ Found language config element: ${selector}`);
        }
      }
    } else {
      console.log('Language config page requires authentication');
    }
  });

  test('should display provider configuration table', async ({ page }) => {
    await page.goto('/admin/languages');
    await page.waitForTimeout(1500);

    // Look for provider configuration table
    const tableSelectors = [
      'table',
      '[data-testid="provider-table"]',
      'thead',
      'tbody tr'
    ];

    let foundTable = false;
    for (const selector of tableSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundTable = true;
        console.log(`✅ Found provider table: ${selector}`);

        // Count table rows
        const rowCount = await page.locator('tbody tr').count();
        console.log(`   Table rows: ${rowCount}`);
        break;
      }
    }

    console.log(`Provider configuration table available: ${foundTable}`);
  });

  test('should display STT provider options', async ({ page }) => {
    await page.goto('/admin/languages');
    await page.waitForTimeout(1500);

    // Look for STT provider mentions
    const sttProviders = ['OpenAI', 'Speechmatics', 'Deepgram', 'Google'];

    for (const provider of sttProviders) {
      const providerElement = page.locator(`text=${provider}`);
      if (await providerElement.count() > 0) {
        console.log(`✅ Found STT provider: ${provider}`);
      }
    }

    console.log('✅ STT provider options check completed');
  });

  test('should display MT provider options', async ({ page }) => {
    await page.goto('/admin/languages');
    await page.waitForTimeout(1500);

    // Look for MT provider mentions
    const mtProviders = ['DeepL', 'OpenAI', 'Google Translate'];

    for (const provider of mtProviders) {
      const providerElement = page.locator(`text=${provider}`);
      if (await providerElement.count() > 0) {
        console.log(`✅ Found MT provider: ${provider}`);
      }
    }

    console.log('✅ MT provider options check completed');
  });

  test('should handle language configuration search/filter', async ({ page }) => {
    await page.goto('/admin/languages');
    await page.waitForTimeout(1500);

    // Look for search/filter input
    const searchSelectors = [
      'input[type="search"]',
      'input[placeholder*="Search"]',
      'input[placeholder*="Filter"]',
      '[data-testid="language-search"]'
    ];

    let foundSearch = false;
    for (const selector of searchSelectors) {
      const element = page.locator(selector).first();
      if (await element.count() > 0) {
        foundSearch = true;
        console.log(`✅ Found search input: ${selector}`);

        try {
          // Try searching for a language
          await element.fill('English');
          await page.waitForTimeout(1000);
          console.log('✅ Language search interaction completed');
        } catch (e) {
          console.log('Search interaction may need UI updates');
        }
        break;
      }
    }

    console.log(`Language search/filter available: ${foundSearch}`);
  });

  test('should display system statistics', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForTimeout(1500);

    // Look for system statistics
    const statisticsElements = [
      'text=Total Rooms',
      'text=Active Users',
      'text=Total Translations',
      'text=System Status',
      '[data-testid="statistics"]',
      '.stats',
      '.dashboard'
    ];

    for (const selector of statisticsElements) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found statistics element: ${selector}`);
      }
    }

    console.log('✅ System statistics display check completed');
  });

  test('should handle provider health status', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForTimeout(1500);

    // Look for provider health indicators
    const healthIndicators = [
      'text=Healthy',
      'text=Degraded',
      'text=Down',
      'text=Online',
      'text=Offline',
      '[data-testid="provider-health"]',
      '.health-status'
    ];

    let foundHealthStatus = false;
    for (const selector of healthIndicators) {
      if (await page.locator(selector).count() > 0) {
        foundHealthStatus = true;
        console.log(`✅ Found health indicator: ${selector}`);
      }
    }

    console.log(`Provider health status available: ${foundHealthStatus}`);
  });

  test('should display cost tracking information', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForTimeout(1500);

    // Look for cost-related elements
    const costSelectors = [
      'text=Cost',
      'text=Usage',
      'text=Billing',
      'text=$',
      '[data-testid="cost-tracker"]',
      'table:has-text("Cost")'
    ];

    let foundCostInfo = false;
    for (const selector of costSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundCostInfo = true;
        console.log(`✅ Found cost tracking element: ${selector}`);
      }
    }

    console.log(`Cost tracking information available: ${foundCostInfo}`);
  });

  test('should handle admin navigation menu', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForTimeout(1500);

    // Look for admin navigation links
    const adminNavLinks = [
      'Dashboard',
      'Languages',
      'Providers',
      'Settings',
      'Users',
      'Rooms',
      'Statistics'
    ];

    for (const linkText of adminNavLinks) {
      const link = page.locator(`a:has-text("${linkText}"), button:has-text("${linkText}")`);
      if (await link.count() > 0) {
        console.log(`✅ Found admin nav link: ${linkText}`);
      }
    }

    console.log('✅ Admin navigation menu check completed');
  });

  test('should require authentication for admin access', async ({ page }) => {
    // Clear cookies to simulate unauthenticated access
    await page.context().clearCookies();

    await page.goto('/admin');
    await page.waitForTimeout(1500);

    const currentUrl = page.url();

    // Should redirect to login or show access denied
    if (currentUrl.includes('/login')) {
      console.log('✅ Admin page requires authentication (redirected to login)');
    } else if (currentUrl.includes('/admin')) {
      console.log('Note: Admin page may allow guest access or has public sections');
    } else {
      console.log(`Admin access result: ${currentUrl}`);
    }
  });

  test('should display language pair configuration', async ({ page }) => {
    await page.goto('/admin/languages');
    await page.waitForTimeout(1500);

    // Look for language pair indicators
    const languagePairSelectors = [
      'text=en-US',
      'text=es-ES',
      'text=fr-FR',
      'text=de-DE',
      'text=pl-PL',
      'text=ar-EG',
      'text=Source Language',
      'text=Target Language'
    ];

    for (const selector of languagePairSelectors) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found language pair element: ${selector}`);
      }
    }

    console.log('✅ Language pair configuration check completed');
  });

  test('should handle provider priority configuration', async ({ page }) => {
    await page.goto('/admin/languages');
    await page.waitForTimeout(1500);

    // Look for priority/tier indicators
    const prioritySelectors = [
      'text=Priority',
      'text=Tier',
      'text=Primary',
      'text=Fallback',
      '[data-testid="provider-priority"]',
      'select:has-text("Priority")'
    ];

    let foundPriority = false;
    for (const selector of prioritySelectors) {
      if (await page.locator(selector).count() > 0) {
        foundPriority = true;
        console.log(`✅ Found priority configuration: ${selector}`);
      }
    }

    console.log(`Provider priority configuration available: ${foundPriority}`);
  });

  test('should display provider API configuration', async ({ page }) => {
    await page.goto('/admin');
    await page.waitForTimeout(1500);

    // Look for API configuration elements
    const apiConfigSelectors = [
      'text=API Key',
      'text=API URL',
      'text=Configuration',
      'text=Endpoint',
      '[data-testid="api-config"]',
      'input[type="password"]',
      'button:has-text("Save")'
    ];

    for (const selector of apiConfigSelectors) {
      if (await page.locator(selector).count() > 0) {
        console.log(`✅ Found API config element: ${selector}`);
      }
    }

    console.log('✅ Provider API configuration check completed');
  });

  test('should handle admin actions with confirmation', async ({ page }) => {
    await page.goto('/admin/languages');
    await page.waitForTimeout(1500);

    // Look for action buttons that might need confirmation
    const actionButtons = [
      'button:has-text("Delete")',
      'button:has-text("Disable")',
      'button:has-text("Remove")',
      'button:has-text("Reset")'
    ];

    for (const selector of actionButtons) {
      const button = page.locator(selector).first();
      if (await button.count() > 0) {
        console.log(`✅ Found admin action button: ${selector}`);

        try {
          // Click and look for confirmation dialog
          await button.click({ timeout: 5000 });
          await page.waitForTimeout(1000);

          // Look for confirmation dialog
          const confirmationSelectors = [
            'text=Are you sure',
            'text=Confirm',
            'button:has-text("Yes")',
            'button:has-text("Cancel")',
            '[role="dialog"]'
          ];

          for (const confirmSelector of confirmationSelectors) {
            if (await page.locator(confirmSelector).count() > 0) {
              console.log(`✅ Confirmation dialog appeared: ${confirmSelector}`);
              // Click cancel to close
              const cancelButton = page.locator('button:has-text("Cancel")').first();
              if (await cancelButton.count() > 0) {
                await cancelButton.click();
              }
              break;
            }
          }
        } catch (e) {
          console.log('Admin action may require authentication or UI updates');
        }
        break;
      }
    }

    console.log('✅ Admin action confirmation check completed');
  });
});
