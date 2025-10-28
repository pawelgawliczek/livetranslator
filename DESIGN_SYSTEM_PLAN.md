# LiveTranslator Design System Implementation Plan

## Overview
This document outlines how we'll apply modern design principles to LiveTranslator, creating a clean, accessible, and professional interface using TailwindCSS and semantic design tokens.

---

## 1. Design Philosophy

### Core Principles
- **Card on clean background aesthetic**: Components float on clean surfaces with subtle elevation
- **Minimalist & lightweight**: No heavy UI frameworks, just TailwindCSS + semantic HTML
- **Consistent spacing rhythm**: Predictable padding and margins throughout
- **Typography hierarchy**: Clear visual scale from h1 to body text
- **Professional polish**: Subtle shadows, smooth transitions, rounded corners

---

## 2. Color System

### Semantic Color Tokens
We'll define a semantic color system that works for LiveTranslator's conversational/collaboration context:

```css
/* Light theme (primary) */
--bg: #fafafa          /* Page background - clean, light gray */
--fg: #1a1a1a          /* Primary text - near black */
--muted: #6b7280       /* Secondary text - gray-500 */
--card: #ffffff        /* Card/surface background - pure white */
--border: #e5e7eb      /* Hairline dividers - gray-200 */
--accent: #667eea      /* Primary CTA/links - purple (current brand) */
--accent-fg: #ffffff   /* Text on accent background */
--ring: #667eea80      /* Focus ring - accent at 50% opacity */

/* Dark theme (optional) */
--bg-dark: #0a0a0a     /* Current dark background */
--fg-dark: #f5f5f5     /* Light text */
--muted-dark: #9ca3af  /* Muted text */
--card-dark: #1a1a1a   /* Card background */
--border-dark: #2a2a2a /* Subtle borders */
--accent-dark: #764ba2 /* Adjusted accent for dark */
```

### Application in LiveTranslator
- **Landing page**: Keep gradient hero (#667eea → #764ba2) but add card sections
- **Rooms page**: Dark background with white/light cards for room listings
- **Modals & Settings**: White cards on semi-transparent backdrop
- **Buttons**: Accent color for primary actions, muted for secondary

---

## 3. Typography System

### Font Stack
```css
--sans: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif
--mono: ui-monospace, "SF Mono", Consolas, "Liberation Mono", Menlo, monospace
```

### Heading Scale
```css
h1: 2.5rem/3rem (40px) - font-bold - Page titles
h2: 2rem/2.5rem (32px) - font-bold - Section headings
h3: 1.5rem/2rem (24px) - font-semibold - Subsections
h4: 1.25rem/1.75rem (20px) - font-semibold - Card titles
h5: 1.125rem/1.5rem (18px) - font-medium - Small headings
h6: 1rem/1.5rem (16px) - font-medium - Labels
body: 1rem/1.5rem (16px) - font-normal - Base text
small: 0.875rem/1.25rem (14px) - Captions, metadata
```

### Application
- **Room titles**: h4
- **Modal headings**: h3
- **Settings sections**: h5
- **Participant names**: body
- **Timestamps**: small + muted

---

## 4. Spacing & Layout

### Container Widths
```css
--container-sm: 640px   /* Forms, modals */
--container-md: 768px   /* Room listings */
--container-lg: 1024px  /* Main app layout */
--container-xl: 1200px  /* Landing page hero */
--prose: 70ch           /* Readable text width */
```

### Spacing Scale (Tailwind default)
```
0.5 = 0.125rem (2px)
1   = 0.25rem (4px)
2   = 0.5rem (8px)
3   = 0.75rem (12px)
4   = 1rem (16px)
6   = 1.5rem (24px)
8   = 2rem (32px)
12  = 3rem (48px)
16  = 4rem (64px)
```

---

## 5. Border Radius

### Rounding Scale
```css
--rounded-sm: 0.5rem   (8px)  - Small elements (tags, pills)
--rounded-md: 0.75rem  (12px) - Buttons, inputs
--rounded-lg: 1rem     (16px) - Cards, modals
--rounded-xl: 1.25rem  (20px) - Large cards, hero sections
--rounded-full: 9999px        - Circular elements (avatars, badges)
```

### Application
- **Room cards**: rounded-lg
- **Buttons**: rounded-md
- **Modals**: rounded-xl
- **Settings menu items**: rounded-md
- **Language selector badge**: rounded-full or rounded-lg

---

## 6. Shadows (Subtle Elevation)

```css
--shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05)           /* Subtle */
--shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1)               /* Card default */
--shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1)         /* Elevated cards */
--shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1)       /* Modals */
--shadow-xl: 0 20px 25px -5px rgba(0, 0, 0, 0.1)       /* Popovers */
```

### Application
- **Room cards**: shadow-md
- **Modals**: shadow-xl
- **Dropdowns**: shadow-lg
- **Hover states**: increase shadow slightly

---

## 7. Component Patterns

### Card Component
```jsx
<Card>
  - Background: --card
  - Border: 1px solid --border
  - Padding: 1.5rem (24px)
  - Border radius: rounded-lg
  - Shadow: shadow-md
  - Hover: shadow-lg + subtle scale
</Card>
```

**Use for**: Room listings, settings panels, participant cards

### Button Component
```jsx
<Button variant="primary">
  - Background: --accent
  - Text: --accent-fg
  - Padding: 0.75rem 1.5rem
  - Border radius: rounded-md
  - Font: font-semibold
  - Shadow: shadow-sm
  - Hover: darken 10%
  - Focus: ring-2 ring-offset-2 ring-accent
</Button>

<Button variant="secondary">
  - Background: transparent
  - Border: 1px solid --border
  - Text: --fg
  - Same padding/radius
</Button>
```

### Section Component
```jsx
<Section>
  - Background: --card
  - Padding: 2rem (32px)
  - Border radius: rounded-xl
  - Max width: --container-lg
  - Margin: 0 auto
</Section>
```

**Use for**: Main content areas on landing page

### Modal Component
```jsx
<Modal>
  - Background: --card
  - Backdrop: rgba(0,0,0,0.5) with backdrop-blur
  - Border radius: rounded-xl
  - Shadow: shadow-xl
  - Max width: --container-sm
  - Padding: 2rem
</Modal>
```

### Tag/Pill Component
```jsx
<TagPill>
  - Background: rgba(--accent, 0.1)
  - Text: --accent (darker shade)
  - Padding: 0.25rem 0.75rem
  - Border radius: rounded-sm or rounded-full
  - Font size: 0.875rem
</TagPill>
```

**Use for**: Room visibility badges (Public/Private), language indicators

### Navigation/Header
```jsx
<AppShell>
  - Sticky top: 0
  - Background: --card with backdrop-blur
  - Border bottom: 1px solid --border
  - Padding: 1rem
  - Layout: flex justify-between
  - Left: Brand/Logo
  - Center: Nav links (optional)
  - Right: User menu + actions
</AppShell>
```

---

## 8. Specific Page Applications

### Landing Page
- **Hero**: Keep gradient background
- **Feature cards**: White cards (--card) floating on gradient
- **Buttons**: Accent color with proper contrast
- **Typography**: Large h1, readable body

### Rooms Page
- **Background**: --bg or dark theme
- **Room cards**: Card component with shadow
- **Create button**: Primary button (accent)
- **Room badges**: TagPill for Public/Private/Shared

### Room Page (Chat/Translation)
- **Header**: AppShell pattern with room info
- **Messages**: Card-like bubbles with proper spacing
- **Input**: Card with border, rounded-lg
- **Participants panel**: Sidebar with card background

### Modals (Settings, Invite, etc.)
- **Container**: Modal component
- **Menu items**: List with hover states (bg-muted/10)
- **Toggles**: Custom styled or Tailwind forms
- **Close button**: Muted with hover accent

### Forms (Login/Signup)
- **Container**: Card component centered
- **Inputs**: Border + rounded-md + focus ring
- **Labels**: font-medium, --muted
- **Submit button**: Primary button

---

## 9. Accessibility Requirements

### Color Contrast
- **Text on background**: ≥ 4.5:1 ratio
- **Large text (18px+)**: ≥ 3:1 ratio
- **Check accent on white**: Ensure readable

### Focus States
```css
focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-accent
```
Apply to all interactive elements: buttons, links, inputs

### Motion
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

### Semantic HTML
- Use `<nav>`, `<main>`, `<section>`, `<article>`, `<footer>`
- Proper heading hierarchy
- ARIA labels where needed (modals, buttons without text)

---

## 10. PWA Theming

### manifest.webmanifest Updates
```json
{
  "name": "LiveTranslator",
  "short_name": "LiveTranslator",
  "theme_color": "#667eea",
  "background_color": "#fafafa",
  "display": "standalone"
}
```

### HTML Head Updates
```html
<meta name="theme-color" content="#667eea">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
```

---

## 11. Implementation Steps

### Phase 1: Setup (Current)
1. Install TailwindCSS and dependencies
2. Create `tailwind.config.js` with custom tokens
3. Create `globals.css` with CSS variables
4. Set up PostCSS configuration

### Phase 2: Design Tokens
1. Define all color tokens
2. Define typography scale
3. Define spacing, shadows, borders

### Phase 3: Component Library
1. Create base components (Card, Button, Section, Modal)
2. Create utility components (TagPill, Avatar, Badge)
3. Document usage patterns

### Phase 4: Page Updates
1. Landing page
2. Rooms listing page
3. Room/chat page
4. Login/Signup forms
5. Modals and overlays

### Phase 5: Polish
1. Test color contrast
2. Verify focus states
3. Test reduced motion
4. Update PWA theme
5. Cross-browser testing

---

## 12. Files to Create/Modify

### New Files
- `web/tailwind.config.js` - Tailwind configuration with tokens
- `web/postcss.config.js` - PostCSS setup
- `web/src/index.css` - Global styles with CSS variables
- `web/src/components/ui/Card.jsx` - Card component
- `web/src/components/ui/Button.jsx` - Button component
- `web/src/components/ui/Section.jsx` - Section component
- `web/src/components/ui/TagPill.jsx` - Tag/badge component

### Modified Files
- `web/package.json` - Add TailwindCSS dependencies
- `web/src/main.jsx` - Import global styles
- `web/index.html` - Update theme-color meta tags
- `web/public/manifest.json` - Update PWA colors
- All page components (*.jsx) - Replace inline styles with Tailwind classes

---

## Summary

This design system will transform LiveTranslator from inline-styled components to a cohesive, professional interface with:
- ✅ Consistent spacing and typography
- ✅ Clean card-based layouts
- ✅ Accessible color contrast and focus states
- ✅ Subtle, professional shadows and borders
- ✅ Smooth transitions and interactions
- ✅ Responsive design patterns
- ✅ Maintainable design tokens

The result will be a modern, polished application that feels professional while maintaining your current brand colors and personality.
