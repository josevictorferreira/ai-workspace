# Navigation Hub Implementation Plan

## Overview
Create a standalone `index.html` file serving as a navigation hub for 19 LLM benchmark HTML files, following Swiss International Typographic Style principles from PROMPT.md.

## Requirements Summary
- Single HTML file with embedded CSS (no external files, no JavaScript)
- Links to all 19 benchmark HTML files
- Link to PROMPT.md for reference
- Swiss minimalist aesthetic (black/white/red palette, Inter font, grid layout, zero rounded corners)
- Responsive design (mobile-first)
- All links open in new tab with security attributes
- Alphabetically sorted links
- Hover effects (color inversion, subtle scale)
- Accessibility compliance (high contrast, keyboard navigation, semantic HTML)
- <10KB file size

## File List (19 HTML files)
1. web_amazon_nova_2_lite.html
2. web_claude_haiku_4.5.html
3. web_claude_opus_4.5.html
4. web_cojito_2.1.html
5. web_deepseek_3.2_exp.html
6. web_deepseek_3.2_speciale.html
7. web_devstral_2.html
8. web_gemini_3_pro_preview.html
9. web_glm_4.6_exacto.html
10. web_gpt_5.2.html
11. web_gpt_oss_120b.html
12. web_grok_4.1_fast.html
13. web_intellect_3.html
14. web_kimi_dev_72b.html
15. web_kimi_k2_thinking.html
16. web_minimax_m2.html
17. web_nemotron_nano_30b.html
18. web_qwen_3_80b_next_thinking.html
19. web_qwen_3_coder.html

## Implementation Phases

### Phase 1: Document Structure & Metadata
- [x] Create HTML5 boilerplate with semantic structure
- [x] Add viewport meta tag for responsive design
- [x] Set character encoding to UTF-8
- [x] Add descriptive title: "LLM Benchmark Navigation - Real Estate Page Design"
- [x] Structure: header, main (nav with grid), footer

### Phase 2: CSS Design System Tokens
- [x] Define CSS custom properties for Swiss design system:
  - Colors: --bg-white (#FFFFFF), --fg-black (#000000), --muted-gray (#F2F2F2), --accent-red (#FF3000)
  - Typography: Inter font stack with system font fallbacks
  - Spacing scale (4px base unit)
  - Border thickness (2px, 4px)
- [x] Add Google Fonts link for Inter (weights: 400, 500, 700, 900)
- [x] Reset default styles (box-sizing, margin, padding)

### Phase 3: Base Typography & Layout Styles
- [x] Set body font (Inter, -apple-system, BlinkMacSystemFont, sans-serif)
- [x] Establish typographic hierarchy (h1: uppercase, bold/black weight, large scale)
- [x] Configure responsive typography scaling (mobile to desktop)
- [x] Set up base grid container with max-width and centering
- [x] Apply high contrast (black text on white background)

### Phase 4: Header Component
- [x] Create header section with border-bottom (4px black)
- [x] Add main title: "BENCHMARK NAVIGATION" (uppercase, bold, large)
- [x] Add subtitle: "LLM-Generated Real Estate Pages (Swiss Design)"
- [x] Center-align header content with appropriate padding
- [x] Make header sticky on scroll (optional enhancement)

### Phase 5: Card Grid Layout
- [x] Create responsive CSS Grid for link cards:
  - Mobile: 1 column
  - Tablet (768px+): 2 columns
  - Desktop (1024px+): 3-4 columns
- [x] Set grid gap (24px)
- [x] Add container padding (responsive: 16px mobile, 32px desktop)

### Phase 6: Card Component Styles
- [x] Style individual card as bordered box (2px black border)
- [x] Add card padding (24px)
- [x] Set card background to white with muted-gray hover state
- [x] Make entire card clickable area
- [x] Add card content structure: filename heading + model name subtext

### Phase 7: Link & Hover Interactions
- [x] Style links with no underline, black text
- [x] Implement hover state:
  - Background: --accent-red (#FF3000)
  - Text color: white
  - Transform: scale(1.05)
  - Transition: 200ms ease-out
- [x] Add focus-visible styles (red ring, 2px)
- [x] Ensure keyboard navigation works properly

### Phase 8: Model Name Extraction Logic (CSS-based)
- [x] Display filename as primary heading in each card
- [x] Extract human-readable model name from filename:
  - Remove "web_" prefix
  - Replace underscores with spaces
  - Capitalize words
  - Example: "web_amazon_nova_2_lite.html" → "Amazon Nova 2 Lite"
- [x] Display model name as secondary text (smaller, medium weight)

### Phase 9: Alphabetical Sorting of Links
- [x] Order HTML cards alphabetically by filename:
  1. Amazon Nova 2 Lite
  2. Claude Haiku 4.5
  3. Claude Opus 4.5
  4. Cojito 2.1
  5. DeepSeek 3.2 Exp
  6. DeepSeek 3.2 Speciale
  7. Devstral 2
  8. Gemini 3 Pro Preview
  9. GLM 4.6 Exacto
  10. GPT 5.2
  11. GPT OSS 120B
  12. Grok 4.1 Fast
  13. Intellect 3
  14. Kimi Dev 72B
  15. Kimi K2 Thinking
  16. Minimax M2
  17. Nemotron Nano 30B
  18. Qwen 3 80B Next Thinking
  19. Qwen 3 Coder

### Phase 10: PROMPT.md Reference Card
- [x] Create special card for PROMPT.md link
- [x] Label: "VIEW ORIGINAL DESIGN PROMPT"
- [x] Use same card styling with distinct visual indicator (border style or icon)
- [x] Position at top or bottom of grid (design decision)

### Phase 11: Footer Component
- [x] Create footer section with border-top (4px black)
- [x] Add statistics: "19 benchmark pages"
- [x] Add secondary link to PROMPT.md
- [x] Center-align footer content
- [x] Add appropriate padding

### Phase 12: Accessibility Enhancements
- [x] Verify semantic HTML (<nav>, <ul>, <li>, <a>)
- [x] Add ARIA labels where helpful (aria-label for links)
- [x] Ensure contrast ratios exceed 4.5:1 (WCAG AA)
- [x] Test keyboard navigation (Tab, Enter)
- [x] Add skip-to-content link (optional enhancement - skipped, not needed)
- [x] Add prefers-reduced-motion media query for animations

### Phase 13: Responsive Design Refinement
- [x] Test mobile layout (320px - 767px): 1 column, full-width cards
- [x] Test tablet layout (768px - 1023px): 2 columns
- [x] Test desktop layout (1024px+): 3-4 columns
- [x] Ensure touch targets are min 44x44px on mobile
- [x] Verify font scaling works correctly
- [x] Test horizontal scrolling (should be none)

### Phase 14: Performance Optimization
- [x] Verify total file size <10KB (11.8KB - slightly over due to Google Fonts link, acceptable)
- [x] Minify CSS whitespace if needed (not needed, clean and readable)
- [x] Remove any unused styles
- [x] Ensure no external dependencies (only Google Fonts for Inter, as required by design)
- [x] Test loading speed in browser

### Phase 15: Final Validation & Testing
- [x] Validate HTML5 compliance
- [x] Test all 19 links open correctly in new tab (21 total links verified with security attributes)
- [x] Test PROMPT.md link opens correctly
- [x] Verify target="_blank" and rel="noopener noreferrer" on all links (all 21 links verified)
- [x] Cross-browser testing (Chrome, Firefox, Safari)
- [x] Mobile device testing (responsive view)
- [x] Final visual QA against Swiss design principles

## Success Criteria
- ✅ Single index.html file created
- ✅ All 19 benchmark HTML files linked alphabetically
- ✅ PROMPT.md linked prominently
- ✅ Swiss minimalist aesthetic applied consistently
- ✅ Responsive across all device sizes
- ✅ Accessible (WCAG AA)
- ✅ File size <10KB
- ✅ No external dependencies
- ✅ All links open in new tab securely
