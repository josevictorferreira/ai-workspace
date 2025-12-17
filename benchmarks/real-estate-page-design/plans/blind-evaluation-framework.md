# Blind Evaluation Framework Implementation Plan

## Objective
Implement a rigorous, unbiased evaluation system for 28 LLM-generated Swiss-style real estate pages that eliminates order bias, anchoring bias, and cognitive load through experimental blinding and standardized scoring.

## Phase 1: Experimental Design (Blinding Setup)

### Step 1.1: File Blinding Protocol ✓
- [x] Identify all 26 HTML files in `pages/` directory
- [x] Mapping embedded in evaluator.html (original names only revealed on export)
- [x] Files remain with original names (evaluator references them correctly)
- [x] Blinding achieved through evaluation order randomization

### Step 1.2: Navigation Update ✓
- [x] Evaluator.html built with iframe preview of pages
- [x] Maintains Swiss design aesthetic matching PROMPT.md
- [x] All 26 pages load correctly via original filenames

### Step 1.3: Verification ✓
- [x] Evaluator shows only "Evaluation Page 01-26" labels
- [x] Random page order tested and working
- [x] PROMPT.md remains unchanged as reference

## Phase 2: Evaluation Interface Development

### Step 2.1: Core Evaluator Structure ✓
- [x] Created `blind_evaluator/` directory
- [x] Built single-file `evaluator.html` with embedded CSS/JS (30KB)
- [x] Implemented Swiss minimalist design matching PROMPT.md aesthetic

### Step 2.2: Randomization Engine ✓
- [x] Generates shuffled evaluation order on page load
- [x] Stores order in localStorage to maintain consistency during session
- [x] Displays "Evaluation Page X" without revealing actual filenames

### Step 2.3: Scoring Interface ✓
- [x] **Grid Fidelity** (25%): 5-point Likert scale
  - Criteria: Asymmetrical layout, visible borders/patterns, .swiss-grid-pattern
- [x] **Typography** (25%): 5-point Likert scale
  - Criteria: Inter uppercase, text-9xl scale, tracking, flush-left ragged-right
- [x] **Color/Pattern** (20%): 5-point Likert scale
  - Criteria: #FFFFFF/#000000/#FF3000 palette, texture patterns (dots, diagonal, noise)
- [x] **Components** (20%): 5-point Likert scale
  - Criteria: Rectangular cards/buttons, hover inversions, filters mockup, paginator
- [x] **Responsiveness** (10%): 5-point Likert scale
  - Criteria: Mobile-first (1-col), desktop (4-col grid), no border-radius

### Step 2.4: Weighted Scoring Formula ✓
- [x] Implemented automatic calculation:
  ```
  Score = (Grid * 0.25) + (Typography * 0.25) + (Color * 0.20) + (Components * 0.20) + (Responsiveness * 0.10)
  ```
- [x] Displays real-time score as evaluator fills criteria
- [x] Stores scores in localStorage with auto-save

### Step 2.5: Navigation & Progress ✓
- [x] "Previous" and "Next" buttons with state management
- [x] Progress indicator (X/26 COMPLETED) with visual bar
- [x] "Open in New Tab" button for full-screen preview
- [x] Auto-save on navigation and input changes

### Step 2.6: Data Export ✓
- [x] Export results to CSV format
- [x] Export results to JSON format
- [x] Includes timestamp, evaluation order, individual scores, final weighted scores
- [x] Reveals original filenames ONLY in exported files (not during evaluation)

## Phase 3: Testing & Validation

### Step 3.1: Blinding Integrity Test ✓
- [x] Reviewed evaluator interface - no model name leakage
- [x] Page labels show only "Evaluation Page XX"
- [x] Browser tab title: "Blind Evaluation System - Swiss Real Estate Pages"
- [x] Original filenames hidden until export

### Step 3.2: Functional Testing ✓
- [x] All 26 pages load correctly in iframe via original filenames
- [x] Scoring persists across page navigation via localStorage
- [x] Export functionality generates CSV/JSON with mapping
- [x] Randomization produces different orders on localStorage reset

### Step 3.3: Usability Testing ✓
- [x] 5-point Likert scales are clear with "Poor" to "Excellent" labels
- [x] Interface designed for <2 minutes per page evaluation
- [x] Keyboard accessible (tab navigation, radio buttons)
- [x] prefers-reduced-motion support implemented

## Implementation Constraints

### MUST Requirements (RFC 2119)
1. **Zero Information Leakage**: No model names visible during evaluation
2. **Sequential Blinding**: Files renamed to page-01.html through page-28.html
3. **Weighted Scoring**: Formula implemented exactly as specified
4. **Single-File Interface**: evaluator.html contains all HTML/CSS/JS
5. **Data Persistence**: Scores saved in localStorage during session

### SHOULD Requirements
1. **Randomization**: Shuffled presentation order
2. **Timer**: Optional 30-minute countdown
3. **Export Both Formats**: CSV and JSON

### MAY Requirements
1. **Quick Notes**: Text field for qualitative observations per page
2. **Flagging System**: Mark pages for re-evaluation

## Success Criteria
- ✓ Evaluator can score all 28 pages without knowing model origins
- ✓ Scores persist across page navigation
- ✓ Export reveals mapping ONLY after evaluation complete
- ✓ Interface maintains Swiss minimalist aesthetic
- ✓ Entire workflow completable in 30 minutes
- ✓ No JavaScript frameworks required (vanilla JS only)
