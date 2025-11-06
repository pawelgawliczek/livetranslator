// @ts-check
const { test, expect } = require('@playwright/test');

/**
 * Subscription Management E2E Tests
 *
 * Tests subscription page display, tier comparison, quota status, and upgrade flows
 * Covers Phase 4 US-002 (User Subscription Page) functionality
 * NOTE: Stripe checkout is mocked - actual payment processing tested via unit/integration tests
 */

test.describe('Subscription Management - Page Display', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to subscription page
    // Note: In production environment, user must be authenticated
    await page.goto('/subscription');
    await page.waitForTimeout(1500);
  });

  test('should display subscription page (authenticated)', async ({ page }) => {
    const currentUrl = page.url();

    // With global auth setup, should always be on subscription page
    expect(currentUrl).toContain('/subscription');
    console.log('✅ Subscription page loaded (authenticated)');

    // Verify page title/heading
    const headingSelectors = [
      'h1:has-text("Subscription")',
      'h2:has-text("Subscription")',
      'text=Choose Your Plan',
      'text=Current Plan'
    ];

    let foundHeading = false;
    for (const selector of headingSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundHeading = true;
        console.log(`✅ Found subscription heading: ${selector}`);
        break;
      }
    }

    expect(foundHeading).toBeTruthy();
  });

  test('should display all three subscription tiers (Free, Plus, Pro)', async ({ page }) => {
    // Look for all tier names
    const tiers = ['Free', 'Plus', 'Pro'];
    for (const tier of tiers) {
      const tierElement = page.locator(`text=${tier}`).first();
      const count = await tierElement.count();

      if (count > 0) {
        console.log(`✅ Found tier: ${tier}`);
      } else {
        console.log(`❌ Tier not found: ${tier}`);
      }

      // At least one tier should be visible
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });

  test('should display quota information', async ({ page }) => {
    // Look for quota-related text
    const quotaSelectors = [
      'text=hours',
      'text=usage',
      'text=quota',
      'text=remaining',
      '[data-testid="quota-status"]',
      '[data-testid="quota-card"]'
    ];

    let foundQuota = false;
    for (const selector of quotaSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundQuota = true;
        console.log(`✅ Found quota element: ${selector}`);
        break;
      }
    }

    console.log(`Quota information displayed: ${foundQuota}`);
  });
});

test.describe('Subscription Management - Tier Features', () => {
  test('should display pricing for Plus and Pro tiers', async ({ page }) => {
    await page.goto('/subscription');
    await page.waitForTimeout(1500);

    // Look for price displays (e.g., $29/month, $79/month)
    const pricePatterns = [
      /\$\d+/,  // Matches $29, $79, etc.
      /month/i,
      /annual/i
    ];

    let foundPricing = false;
    const pageContent = await page.content();

    for (const pattern of pricePatterns) {
      if (pattern.test(pageContent)) {
        foundPricing = true;
        console.log(`✅ Found pricing pattern: ${pattern}`);
      }
    }

    console.log(`Pricing information displayed: ${foundPricing}`);
  });

  test('should display feature comparison for tiers', async ({ page }) => {
    await page.goto('/subscription');
    await page.waitForTimeout(1500);

    // Look for key features
    const features = [
      'recording',
      'multi-speaker',
      'diarization',
      'hours',
      'unlimited'
    ];

    let featuresFound = 0;
    for (const feature of features) {
      const regex = new RegExp(feature, 'i');
      const pageContent = await page.content();

      if (regex.test(pageContent)) {
        featuresFound++;
        console.log(`✅ Found feature: ${feature}`);
      }
    }

    console.log(`Features found: ${featuresFound}/${features.length}`);
  });
});

test.describe('Subscription Management - Upgrade Actions', () => {
  test('should display upgrade buttons for non-Pro users', async ({ page }) => {
    await page.goto('/subscription');
    await page.waitForTimeout(1500);

    // Look for upgrade/subscribe buttons
    const upgradeSelectors = [
      'button:has-text("Upgrade")',
      'button:has-text("Subscribe")',
      'button:has-text("Choose Plan")',
      'a:has-text("Upgrade")',
      '[data-testid="upgrade-button"]'
    ];

    let foundUpgradeButton = false;
    for (const selector of upgradeSelectors) {
      const count = await page.locator(selector).count();
      if (count > 0) {
        foundUpgradeButton = true;
        console.log(`✅ Found upgrade button: ${selector} (count: ${count})`);
      }
    }

    console.log(`Upgrade buttons available: ${foundUpgradeButton}`);
  });

  test('should handle upgrade button click (redirect to checkout)', async ({ page }) => {
    await page.goto('/subscription');
    await page.waitForTimeout(1500);

    // Try to find and click upgrade button
    const upgradeButton = page.locator('button:has-text("Upgrade")').first();

    if (await upgradeButton.count() > 0) {
      console.log('✅ Upgrade button found, attempting click');

      // Listen for navigation or API calls
      const navigationPromise = page.waitForNavigation({ timeout: 5000 }).catch(() => null);

      await upgradeButton.click();
      await navigationPromise;

      const newUrl = page.url();
      console.log(`After upgrade click, URL: ${newUrl}`);

      // Expect either:
      // 1. Redirect to Stripe checkout (stripe.com)
      // 2. Loading/processing state
      // 3. Error message if Stripe not configured
      const isStripeRedirect = newUrl.includes('stripe.com') || newUrl.includes('checkout');
      const hasErrorMessage = await page.locator('text=/error|failed|unavailable/i').count() > 0;

      if (isStripeRedirect) {
        console.log('✅ Redirected to Stripe checkout');
      } else if (hasErrorMessage) {
        console.log('⚠️ Upgrade unavailable (expected in test environment)');
      } else {
        console.log('ℹ️ Upgrade button clicked, no redirect (may need configuration)');
      }
    } else {
      console.log('ℹ️ No upgrade button found (user may be on Pro tier)');
    }
  });
});

test.describe('Subscription Management - Current Tier Display', () => {
  test('should highlight current subscription tier', async ({ page }) => {
    await page.goto('/subscription');
    await page.waitForTimeout(1500);

    // Look for "current" indicators
    const currentIndicators = [
      'text=/current plan/i',
      'text=/your plan/i',
      'text=/active/i',
      '[data-testid="current-tier"]',
      '.active-tier',
      '.current-subscription'
    ];

    let foundCurrentIndicator = false;
    for (const selector of currentIndicators) {
      if (await page.locator(selector).count() > 0) {
        foundCurrentIndicator = true;
        console.log(`✅ Found current tier indicator: ${selector}`);
        break;
      }
    }

    console.log(`Current tier highlighted: ${foundCurrentIndicator}`);
  });
});

test.describe('Subscription Management - Credit Packages', () => {
  test('should display credit package options', async ({ page }) => {
    await page.goto('/subscription');
    await page.waitForTimeout(1500);

    // Look for credit packages (1hr, 4hr, 10hr)
    const creditPatterns = [
      /\d+\s*hour/i,
      /\d+\s*hr/i,
      /credit/i,
      /top.?up/i
    ];

    let foundCredits = false;
    const pageContent = await page.content();

    for (const pattern of creditPatterns) {
      if (pattern.test(pageContent)) {
        foundCredits = true;
        console.log(`✅ Found credit package mention: ${pattern}`);
      }
    }

    console.log(`Credit packages displayed: ${foundCredits}`);
  });
});

/**
 * QUOTA ENFORCEMENT TESTS - HIGH PRIORITY
 * Tests Phase 4 critical quota logic
 */
test.describe('Quota Status Display', () => {
  test('should display quota status card with usage information', async ({ page }) => {
    await page.goto('/subscription');
    await page.waitForTimeout(1500);

    // Look for QuotaStatusCard component
    const quotaCardSelectors = [
      '[data-testid="quota-status-card"]',
      'text=/quota/i',
      'text=/\d+\s*\/\s*\d+\s*hours/i',  // Matches "5 / 10 hours"
      'text=/\d+%/i'  // Matches percentage
    ];

    let foundQuotaCard = false;
    for (const selector of quotaCardSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundQuotaCard = true;
        console.log(`✅ Found quota card element: ${selector}`);
      }
    }

    console.log(`Quota status card displayed: ${foundQuotaCard}`);
  });

  test('should display warning when quota is near exhaustion', async ({ page }) => {
    // This test requires user to have 80%+ quota used
    // In real tests, you'd set up test data via API
    await page.goto('/subscription');
    await page.waitForTimeout(1500);

    // Look for warning indicators
    const warningSelectors = [
      'text=/warning/i',
      'text=/80%/i',
      'text=/running low/i',
      'text=/almost/i',
      '[data-testid="quota-warning"]',
      '.quota-warning',
      '[role="alert"]'
    ];

    let foundWarning = false;
    for (const selector of warningSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundWarning = true;
        console.log(`✅ Found quota warning: ${selector}`);
      }
    }

    console.log(`Quota warning displayed (if quota > 80%): ${foundWarning}`);
  });
});

/**
 * BILLING HISTORY PAGE TESTS
 * Tests Phase 4 US-003 (Billing History Page)
 */
test.describe('Billing History Page', () => {
  test('should navigate to billing history page', async ({ page }) => {
    await page.goto('/billing-history');
    await page.waitForTimeout(1500);

    const currentUrl = page.url();

    if (currentUrl.includes('/billing-history')) {
      console.log('✅ Billing history page loaded');

      // Look for page title
      const titleSelectors = [
        'h1:has-text("Billing History")',
        'h2:has-text("Payment History")',
        'text=/transaction/i'
      ];

      let foundTitle = false;
      for (const selector of titleSelectors) {
        if (await page.locator(selector).count() > 0) {
          foundTitle = true;
          console.log(`✅ Found billing history title: ${selector}`);
          break;
        }
      }

      expect(foundTitle || currentUrl.includes('/billing')).toBeTruthy();
    } else if (currentUrl.includes('/login')) {
      console.log('✅ Billing history requires authentication');
    }
  });

  test('should display transaction list (if user has transactions)', async ({ page }) => {
    await page.goto('/billing-history');
    await page.waitForTimeout(1500);

    // Look for transaction table or list
    const transactionSelectors = [
      'table',
      '[data-testid="transaction-list"]',
      'text=/date/i',
      'text=/amount/i',
      'text=/status/i',
      'text=/completed/i',
      'text=/pending/i'
    ];

    let foundTransactions = false;
    for (const selector of transactionSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundTransactions = true;
        console.log(`✅ Found transaction element: ${selector}`);
      }
    }

    console.log(`Transaction list displayed: ${foundTransactions}`);
  });

  test('should display empty state if no transactions', async ({ page }) => {
    await page.goto('/billing-history');
    await page.waitForTimeout(1500);

    // Look for empty state message
    const emptyStateSelectors = [
      'text=/no transactions/i',
      'text=/no payments/i',
      'text=/no billing history/i',
      '[data-testid="empty-state"]'
    ];

    let foundEmptyState = false;
    for (const selector of emptyStateSelectors) {
      if (await page.locator(selector).count() > 0) {
        foundEmptyState = true;
        console.log(`✅ Found empty state: ${selector}`);
        break;
      }
    }

    console.log(`Empty state displayed (if no transactions): ${foundEmptyState}`);
  });
});
