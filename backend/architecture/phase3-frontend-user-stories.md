# Phase 3: Admin Panel Frontend - User Stories

**Created:** 2025-11-04
**Phase:** Phase 3 (Admin Panel Frontend)
**Status:** Ready for Architect Review
**Total Stories:** 18
**Estimated Effort:** 50-70 developer days

---

## Story Summary

**Priority Breakdown:**
- P0 (Critical): 6 stories
- P1 (High): 11 stories
- P2 (Nice-to-have): 1 story

**Estimate Breakdown:**
- XS (<1 day): 1 story
- S (1-3 days): 6 stories
- M (3-5 days): 8 stories
- L (5-7 days): 3 stories

---

## 1. OVERVIEW DASHBOARD

### US-001: View Admin Dashboard Overview

**As a** business owner,
**I want to** see a comprehensive dashboard with key metrics at a glance,
**So that** I can quickly assess overall business health without navigating multiple pages.

**Acceptance Criteria:**
- [ ] Dashboard displays 8 metric cards in grid layout (2x4):
  - Total Revenue (MTD)
  - Total Costs (MTD)
  - Gross Profit (MTD)
  - Gross Margin % (with color coding: red <30%, yellow 30-40%, green >40%)
  - Active Users (DAU)
  - Total Rooms Created (MTD)
  - Avg Cost per User
  - Provider Health Status (healthy/degraded/down)
- [ ] Each card shows trend indicator (↑/↓) vs last period
- [ ] Cards refresh every 60 seconds
- [ ] Quick links to detailed pages (Financial, Users, System)
- [ ] Date range selector (Today, Last 7d, Last 30d, Custom)
- [ ] All data loads within 2 seconds
- [ ] Empty state if no data for selected period
- [ ] Non-admin users redirected to /rooms with 403 error toast

**Priority:** P0 (launch blocker)
**Estimate:** L (5-7 days)

---

## 2. FINANCIAL ANALYTICS

### US-002: View Financial Summary Dashboard

**As a** business owner,
**I want to** see detailed financial metrics with revenue vs cost breakdown,
**So that** I can monitor profitability and identify cost optimization opportunities.

**Acceptance Criteria:**
- [ ] Page shows 4 summary cards: Total Revenue, Total Costs, Gross Profit, Gross Margin %
- [ ] Margin card color-coded: red (<30%), yellow (30-40%), green (>40%)
- [ ] Time series chart displays revenue vs cost over selected period (last 30d default)
- [ ] Chart supports date range picker: Last 7d, 30d, 90d, Custom
- [ ] Revenue breakdown by platform: Stripe, Apple IAP, Credit usage
- [ ] All amounts display in USD with 2 decimal precision
- [ ] Data aggregates by day (default), week, or month based on range
- [ ] Export button generates CSV with financial data
- [ ] Empty state message if no transactions in period
- [ ] Loading spinner while fetching data
- [ ] Error toast if API call fails

**API Endpoint:** GET /api/admin/financial/summary

**Priority:** P0 (launch blocker)
**Estimate:** M (3-5 days)

---

### US-003: Analyze Tier Profitability

**As a** product manager,
**I want to** see profitability analysis by subscription tier (Free/Plus/Pro),
**So that** I can understand which tiers are profitable and optimize pricing strategy.

**Acceptance Criteria:**
- [ ] Table displays tier analysis with columns: Tier Name, Active Users, MRR, Avg Quota Used, Total Cost, Profit per User
- [ ] Each tier row color-coded: red (negative profit), yellow (low margin), green (profitable)
- [ ] Profit per User calculation: (Revenue - Cost) / User Count
- [ ] Quota usage shows average % of allocated quota consumed
- [ ] Sort by any column (default: profit per user descending)
- [ ] Date range filter (default: current month)
- [ ] Tooltip on hover shows detailed breakdown
- [ ] Empty state if no active subscriptions
- [ ] Export to CSV button
- [ ] Refreshes when date range changes

**API Endpoint:** GET /api/admin/financial/tier-analysis

**Priority:** P1 (high value)
**Estimate:** M (3-5 days)

---

## 3. USER ANALYTICS

### US-004: View User Acquisition Metrics

**As a** product manager,
**I want to** see user signup trends and activation rates,
**So that** I can measure marketing effectiveness and onboarding success.

**Acceptance Criteria:**
- [ ] Line chart displays new signups per day over selected period (last 30d default)
- [ ] Displays 3 metrics: New Signups, Activated Users, Fast Activation (<1hr)
- [ ] Activation defined as: user created at least 1 room
- [ ] Fast activation: activated within 1 hour of signup
- [ ] Chart supports date range: Last 7d, 30d, 90d, Custom
- [ ] Summary cards show totals: Total Signups, Activation Rate %, Fast Activation %
- [ ] Table below chart shows daily breakdown
- [ ] Export to CSV with all metrics
- [ ] Empty state if no signups in period
- [ ] Chart tooltips show detailed data on hover

**API Endpoint:** GET /api/admin/users/acquisition

**Priority:** P1 (high value)
**Estimate:** M (3-5 days)

---

### US-005: Monitor User Engagement (DAU/WAU/MAU)

**As a** product manager,
**I want to** see daily, weekly, and monthly active user metrics,
**So that** I can track product engagement and user retention trends.

**Acceptance Criteria:**
- [ ] Three metric cards: DAU, WAU (7-day), MAU (30-day)
- [ ] Line chart shows DAU trend over last 30 days
- [ ] Engagement ratio displayed: DAU/MAU (stickiness metric)
- [ ] Breakdown by user type: Paying vs Free users
- [ ] Date range selector (last 30d, 90d, custom)
- [ ] Table shows daily breakdown with user counts
- [ ] Export to CSV with all engagement data
- [ ] Tooltips explain metric definitions
- [ ] Empty state if no activity in period
- [ ] Loading state with skeleton UI

**API Endpoint:** GET /api/admin/users/engagement

**Priority:** P1 (high value)
**Estimate:** M (3-5 days)

---

### US-006: Analyze User Retention Cohorts

**As a** product manager,
**I want to** see cohort retention rates (Day 1, Day 7, Day 30),
**So that** I can measure product stickiness and identify retention improvement opportunities.

**Acceptance Criteria:**
- [ ] Cohort table displays retention by signup date
- [ ] Columns: Cohort Date, Cohort Size, Day 1 %, Day 7 %, Day 30 %
- [ ] Retention % color-coded: red (<20%), yellow (20-40%), green (>40%)
- [ ] Heatmap visualization option for retention grid
- [ ] Date range filter (last 90 days default for cohort formation)
- [ ] Tooltips explain retention calculation
- [ ] Export to CSV with cohort data
- [ ] Sort by any column
- [ ] Empty state if no cohorts in period
- [ ] Loading spinner during data fetch

**API Endpoint:** GET /api/admin/users/retention

**Priority:** P1 (high value)
**Estimate:** L (5-7 days)

---

## 4. SYSTEM MONITORING

### US-007: View System Performance Metrics

**As a** product manager,
**I want to** see provider-level performance metrics (costs, request counts),
**So that** I can monitor system health and identify performance bottlenecks.

**Acceptance Criteria:**
- [ ] Table displays provider performance: Service (STT/MT), Provider, Request Count, Avg Cost, Total Cost
- [ ] Breakdown by STT providers: Speechmatics, Google v2, Azure, Soniox, OpenAI
- [ ] Breakdown by MT providers: DeepL, Google Translate, Amazon Translate, OpenAI
- [ ] Date range filter (last 24h default)
- [ ] Sort by request count or total cost
- [ ] Warning badge if provider has >5% error rate
- [ ] Export to CSV with performance data
- [ ] Note displayed: "Latency metrics unavailable (requires future migration)"
- [ ] Empty state if no requests in period
- [ ] Refresh button to update data

**API Endpoint:** GET /api/admin/system/performance

**Priority:** P1 (high value)
**Estimate:** S (1-3 days)

---

### US-008: Monitor Quota Utilization

**As a** product manager,
**I want to** see quota usage by tier,
**So that** I can identify over/under-utilized tiers and optimize quota allocations.

**Acceptance Criteria:**
- [ ] Table displays: Tier Name, Total Users, Avg Quota Used %, Total Used Hours, Total Allocated Hours
- [ ] Quota utilization color-coded: red (>90%), yellow (70-90%), green (<70%)
- [ ] Progress bar shows % used of allocated quota per tier
- [ ] Date range filter (default: current billing period)
- [ ] Warning if any tier consistently exceeds 90% usage
- [ ] Export to CSV with utilization data
- [ ] Summary cards: Total Quota Used, Avg Utilization %, Top Tier by Usage
- [ ] Empty state if no quota usage in period
- [ ] Refresh every 60 seconds

**API Endpoint:** GET /api/admin/system/quota-utilization

**Priority:** P1 (high value)
**Estimate:** S (1-3 days)

---

## 5. ADMIN TOOLS

### US-009: Search and View User Details

**As** customer support,
**I want to** search for users by email or ID,
**So that** I can quickly access user information for support requests.

**Acceptance Criteria:**
- [ ] Search box with placeholder "Search by email or user ID"
- [ ] Search triggers on Enter or button click
- [ ] Search results display: User ID, Email, Display Name, Tier, Quota Used, Signup Date
- [ ] Click on user row opens detail modal
- [ ] Modal shows: Full profile, subscription details, quota balance, activity history
- [ ] Empty state if no results found
- [ ] Error toast if search fails
- [ ] Debounce search input (500ms)
- [ ] Clear button to reset search
- [ ] Loading spinner during search

**Priority:** P0 (critical for support)
**Estimate:** M (3-5 days)

---

### US-010: Grant Bonus Credits to User

**As** customer support,
**I want to** grant bonus quota hours to users,
**So that** I can resolve support issues and provide compensation.

**Acceptance Criteria:**
- [ ] "Grant Credits" button in user detail modal
- [ ] Form fields: Hours to Grant (number input), Reason (textarea, required)
- [ ] Validation: Hours must be > 0 and <= 100
- [ ] Confirmation dialog: "Grant {X} hours to {user_email}?"
- [ ] Success toast: "Granted {X} hours to {user}"
- [ ] Creates quota_transaction record with admin metadata
- [ ] Creates admin_audit_log entry
- [ ] Updates user's bonus_credits_seconds in database
- [ ] Modal closes and user list refreshes on success
- [ ] Error toast if grant fails
- [ ] Disabled state during submission
- [ ] Reason field required (min 10 characters)

**API Endpoint:** POST /api/admin/users/{user_id}/grant-credits

**Priority:** P0 (critical for support)
**Estimate:** M (3-5 days)

---

### US-011: View Active Rooms with Participants

**As** customer support,
**I want to** see currently active rooms with participant counts,
**So that** I can monitor live usage and troubleshoot issues in real-time.

**Acceptance Criteria:**
- [ ] Table displays: Room Code, Owner Email, Participant Count, Last Activity, Is Multi-Speaker
- [ ] Default filter: Rooms active in last 24 hours
- [ ] Date range filter: Last 1h, 6h, 24h, 7d, Custom
- [ ] Sort by: Last Activity (default), Participant Count, Created At
- [ ] Pagination: 50 rooms per page
- [ ] Click on room code opens room detail modal
- [ ] Room detail modal shows: Room info, active participants, cost summary
- [ ] Empty state if no active rooms in period
- [ ] Refresh button updates data
- [ ] Loading spinner during fetch

**API Endpoint:** GET /api/admin/rooms/active

**Priority:** P1 (support efficiency)
**Estimate:** M (3-5 days)

---

### US-012: Debug Message Details

**As** customer support,
**I want to** view detailed debug information for specific messages (segment_id),
**So that** I can troubleshoot transcription/translation issues reported by users.

**Acceptance Criteria:**
- [ ] Search form: Room Code (input), Segment ID (number input)
- [ ] "Fetch Debug Info" button
- [ ] Debug info displays: STT details, MT details, cost breakdown, routing info
- [ ] STT section: Provider used, language, latency, audio duration, cost, fallback status
- [ ] MT section: Provider used, language pair, latency, cost, routing reason, throttle status
- [ ] Cost summary: STT cost, MT cost, total cost
- [ ] Source indicator: Redis (live) or Database (reconstructed)
- [ ] Note if reconstructed: "Latency/routing details unavailable for old messages"
- [ ] Copy button to copy JSON debug data
- [ ] Error toast if segment not found
- [ ] Loading spinner during fetch

**API Endpoint:** GET /api/admin/message-debug/{room_code}/{segment_id}

**Priority:** P2 (nice-to-have, already exists in backend)
**Estimate:** S (1-3 days)

---

## 6. ACCESS CONTROL

### US-013: Enforce Admin-Only Routes

**As a** security admin,
**I want** all admin routes protected with authentication and role checks,
**So that** only authorized admins can access sensitive business data.

**Acceptance Criteria:**
- [ ] All `/admin/*` routes require valid JWT token
- [ ] Routes check `is_admin=true` flag in user record
- [ ] Non-admin users redirected to /rooms with 403 error toast
- [ ] Token expiration handled gracefully (redirect to login)
- [ ] Admin role verified on every API call (backend enforcement)
- [ ] Frontend checks admin role before rendering navigation
- [ ] Admin menu only visible to admin users
- [ ] Unauthorized access attempts logged (backend audit log)
- [ ] Session timeout after 30 minutes of inactivity
- [ ] Re-authentication required after timeout

**Priority:** P0 (security critical)
**Estimate:** S (1-3 days)

---

### US-014: Admin Navigation Menu

**As an** admin user,
**I want** a dedicated admin navigation menu,
**So that** I can easily navigate between different admin panel pages.

**Acceptance Criteria:**
- [ ] Admin menu appears in main navigation (only for admin users)
- [ ] Menu items: Overview, Financial, Users, Metrics, System, Tools
- [ ] Active page highlighted in menu
- [ ] Dropdown submenu for related pages (e.g., Users: Acquisition, Engagement, Retention)
- [ ] Breadcrumb navigation shows current location
- [ ] Quick stats in menu header (e.g., DAU, Margin %)
- [ ] Responsive design: collapses to hamburger on mobile
- [ ] Keyboard navigation support (Tab, Enter)
- [ ] Logout button in admin menu
- [ ] Profile link returns to main user profile

**Priority:** P0 (usability critical)
**Estimate:** M (3-5 days)

---

## 7. DATA EXPORT & FILTERING

### US-015: Export Data to CSV

**As a** finance admin,
**I want to** export financial and user data to CSV,
**So that** I can perform offline analysis and create custom reports.

**Acceptance Criteria:**
- [ ] "Export CSV" button on all analytics pages
- [ ] CSV includes all visible data (respects current filters)
- [ ] Filename format: `livetranslator_[report_type]_[date_range].csv`
- [ ] CSV columns match table columns
- [ ] Numbers formatted with proper precision (2 decimals for currency)
- [ ] Dates in ISO format (YYYY-MM-DD)
- [ ] Download triggers immediately (no server-side processing)
- [ ] Success toast: "Exported {N} rows to CSV"
- [ ] Error toast if export fails
- [ ] Large datasets (>1000 rows) show warning: "This may take a moment"

**Priority:** P1 (regulatory requirement)
**Estimate:** XS (< 1 day)

---

### US-016: Filter Data by Date Range

**As any** admin user,
**I want to** filter all analytics by custom date ranges,
**So that** I can analyze specific time periods (e.g., last quarter, specific campaign).

**Acceptance Criteria:**
- [ ] Date range picker component on all analytics pages
- [ ] Preset options: Today, Last 7d, Last 30d, Last 90d, This Month, Last Month, Custom
- [ ] Custom range: Start Date + End Date pickers
- [ ] Date range validates: Start <= End
- [ ] Date range persists in URL query params
- [ ] Date range updates all charts and tables on change
- [ ] Loading spinner during data refresh
- [ ] Default range: Last 30 days
- [ ] Max range: 1 year
- [ ] Error toast if range exceeds max

**Priority:** P0 (core functionality)
**Estimate:** S (1-3 days)

---

## 8. SYSTEM HEALTH & METRICS

### US-017: View Success KPIs Dashboard

**As a** product manager,
**I want to** see key success metrics (DAU/WAU/MAU, conversion rates, churn),
**So that** I can measure product-market fit and growth trajectory.

**Acceptance Criteria:**
- [ ] Dashboard displays 6 KPI cards:
  - DAU/WAU/MAU (with stickiness ratio)
  - Conversion Rate (Free → Paid)
  - Monthly Recurring Revenue (MRR)
  - Churn Rate (% users canceled)
  - Avg Revenue per User (ARPU)
  - Customer Lifetime Value (LTV)
- [ ] Each KPI shows trend (↑/↓) vs last period
- [ ] Color-coding: Green (improving), Red (degrading), Gray (stable)
- [ ] Tooltips explain calculation methodology
- [ ] Date range filter (last 30d, 90d, custom)
- [ ] Line chart shows KPI trends over time
- [ ] Export to CSV with all KPI data
- [ ] Empty state if insufficient data
- [ ] Refresh every 5 minutes

**Priority:** P1 (strategic insights)
**Estimate:** L (5-7 days)

---

### US-018: Monitor Provider Health Status

**As a** product manager,
**I want to** see real-time provider health status,
**So that** I can quickly identify and respond to service degradations.

**Acceptance Criteria:**
- [ ] Health status table: Provider, Service Type (STT/MT), Status, Consecutive Failures, Last Check, Response Time
- [ ] Status badge: Green (healthy), Yellow (degraded), Red (down)
- [ ] Degraded: 1-2 consecutive failures
- [ ] Down: 3+ consecutive failures
- [ ] "Reset Health" button per provider (admin action)
- [ ] Confirmation dialog: "Mark provider as healthy?"
- [ ] Reset clears consecutive failures counter
- [ ] Auto-refresh every 30 seconds
- [ ] Alert badge in header if any provider is down
- [ ] Export to CSV with health history
- [ ] Empty state if no providers configured

**Priority:** P1 (operational visibility)
**Estimate:** S (1-3 days)

---

## Implementation Order (Recommended)

**Phase 3A: Foundation (P0, 2 weeks)**
1. US-013: Access control (security)
2. US-014: Navigation menu (usability)
3. US-016: Date filtering (core)
4. US-001: Overview dashboard (entry point)

**Phase 3B: Core Analytics (P0/P1, 3-4 weeks)**
5. US-002: Financial summary
6. US-003: Tier profitability
7. US-004: User acquisition
8. US-005: User engagement
9. US-006: User retention

**Phase 3C: Tools & Monitoring (P0/P1, 2-3 weeks)**
10. US-009: User search
11. US-010: Grant credits
12. US-011: Active rooms
13. US-007: System performance
14. US-008: Quota utilization

**Phase 3D: Polish & Export (P1/P2, 1 week)**
15. US-015: CSV export
16. US-017: KPIs dashboard
17. US-018: Provider health
18. US-012: Message debug (if time permits)

**Total Timeline:** 8-10 weeks (2-2.5 months)

---

## Testing Requirements

**Unit Tests (Vitest):**
- Component rendering with props
- User interaction handlers
- Data formatting utilities
- Calculation functions
- Target: 95%+ coverage

**Integration Tests:**
- API client integration
- Data fetching and caching
- Error handling flows
- Authentication/authorization
- Target: 90%+ coverage

**E2E Tests (Playwright):**
- Admin login flow
- View financial dashboard
- Export CSV
- Grant credits to user
- Date range filtering
- Target: Critical paths covered

---

## Files to Create

**Pages:**
- `web/src/pages/AdminOverviewPage.jsx` - US-001
- `web/src/pages/AdminFinancialPage.jsx` - US-002, US-003
- `web/src/pages/AdminUsersPage.jsx` - US-004, US-005, US-006
- `web/src/pages/AdminMetricsPage.jsx` - US-017
- `web/src/pages/AdminSystemPage.jsx` - US-007, US-008, US-018
- `web/src/pages/AdminToolsPage.jsx` - US-009, US-010, US-011, US-012

**Components:**
- `web/src/components/admin/AdminLayout.jsx` - US-014
- `web/src/components/admin/MetricCard.jsx` - Reusable
- `web/src/components/admin/TimeSeriesChart.jsx` - Reusable
- `web/src/components/admin/TierTable.jsx` - US-003
- `web/src/components/admin/CohortTable.jsx` - US-006
- `web/src/components/admin/DateRangePicker.jsx` - US-016
- `web/src/components/admin/ExportButton.jsx` - US-015
- `web/src/components/admin/ProviderHealthBadge.jsx` - US-018
- `web/src/components/admin/UserSearchModal.jsx` - US-009
- `web/src/components/admin/GrantCreditsModal.jsx` - US-010

**Utilities:**
- `web/src/utils/adminApi.js` - API client for all admin endpoints
- `web/src/utils/adminFormatters.js` - Data formatting (currency, percentages)
- `web/src/utils/adminCalculations.js` - KPI calculations
- `web/src/utils/csvExport.js` - CSV generation logic

**Routes:**
- Update `web/src/main.jsx` with admin routes

---

**Document Version:** 1.0
**Last Updated:** 2025-11-04
**Status:** Ready for Architect Review → PM Approval → Development
