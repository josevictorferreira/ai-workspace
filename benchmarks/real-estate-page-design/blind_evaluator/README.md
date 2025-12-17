# Blind Evaluation System for LLM-Generated Swiss Real Estate Pages

## Overview

This is a rigorous, bias-free evaluation framework designed to assess 26 LLM-generated Swiss International Typographic Style real estate property listing pages. The system eliminates three primary threats to validity:

1. **Order Bias**: Prevents evaluator fatigue from affecting later pages
2. **Anchoring Bias**: Ensures absolute assessment against criteria, not relative comparison
3. **Cognitive Load**: Uses simple 5-point Likert scales for consistent scoring

## How It Works

### Blinding Protocol

The system maintains **complete evaluator blinding** throughout the assessment process:

- Pages are presented in **randomized order** (shuffled on first load)
- Only generic labels shown: "Evaluation Page 01", "Evaluation Page 02", etc.
- Model identities are **revealed only in exported results** after evaluation is complete
- Original filenames are hidden from view during scoring

### Scoring System

Each page is evaluated across **5 criteria** using 5-point Likert scales (1 = Poor, 5 = Excellent):

| Criterion | Weight | Description |
|-----------|--------|-------------|
| **Grid Fidelity** | 25% | Asymmetrical layout, visible borders/patterns, grid structure |
| **Typography** | 25% | Inter uppercase, massive scale (text-9xl), tracking, flush-left alignment |
| **Color/Pattern** | 20% | #FFFFFF/#000000/#FF3000 palette, texture patterns (dots, diagonal, noise) |
| **Components** | 20% | Rectangular cards/buttons, hover inversions, filters, paginator |
| **Responsiveness** | 10% | Mobile-first (1-col), desktop (4-col grid), no border-radius |

**Weighted Score Formula:**
```
Score = (Grid × 0.25) + (Typography × 0.25) + (Color × 0.20) + (Components × 0.20) + (Responsiveness × 0.10)
```

Maximum possible score: **5.00**

## Usage Instructions

### Step 1: Open the Evaluator

```bash
# Navigate to the blind_evaluator directory
cd blind_evaluator

# Open evaluator.html in your browser
# (Double-click the file or use: python -m http.server 8000)
```

### Step 2: Evaluate Pages

1. **Preview**: Each page loads in an iframe. Click "Open in New Tab" for full-screen view
2. **Score**: Rate each of the 5 criteria using the Likert scales (1-5)
3. **Notes**: Add optional qualitative observations in the text area
4. **Navigate**: Click "Next →" to move to the next page (scores auto-save)
5. **Progress**: Track completion via the progress bar at the top

**Time Allocation**: Aim for ~2 minutes per page (total: ~50 minutes for 26 pages)

### Step 3: Export Results

When evaluation is complete:

1. Click **"Export CSV"** or **"Export JSON"** at the bottom
2. Model identities are revealed only in the exported file
3. Results include:
   - Evaluation order (randomized sequence)
   - Individual criterion scores
   - Weighted final scores
   - Original filename mapping

### Step 4: Reset (Optional)

Click **"Reset All Evaluations"** to clear localStorage and start fresh with a new randomized order.

## Data Persistence

- Scores are saved automatically in **localStorage** after each page navigation
- You can close and reopen the browser - progress persists
- Randomization order is locked after first load (consistent across session)

## File Structure

```
blind_evaluator/
├── evaluator.html          # Single-file evaluation interface (HTML + CSS + JS)
└── README.md              # This file
```

## Export Format Examples

### CSV Export
```csv
Evaluation Order,Blinded ID,Original Filename,Grid,Typography,Color/Pattern,Components,Responsiveness,Weighted Score,Notes
1,page-15.html,web_intellect_3.html,4,5,3,4,5,4.15,"Excellent grid, minor color issues"
2,page-03.html,web_claude_opus_4.5.html,5,5,5,5,4,4.90,"Near perfect implementation"
...
```

### JSON Export
```json
{
  "metadata": {
    "timestamp": "2025-12-16T20:30:00.000Z",
    "totalPages": 26,
    "completedPages": 26
  },
  "evaluationOrder": [
    {
      "evaluationPosition": 1,
      "blindedId": "page-15.html",
      "originalFilename": "web_intellect_3.html",
      "scores": {
        "grid": 4,
        "typography": 5,
        "color": 3,
        "components": 4,
        "responsiveness": 5,
        "notes": "Excellent grid, minor color issues",
        "weightedScore": 4.15
      }
    }
  ]
}
```

## Statistical Validity

This framework addresses core psychometric challenges:

### Bias Mitigation
- **Blinding**: Model names hidden until export
- **Randomization**: Pages presented in shuffled order
- **Standardization**: Fixed criteria with clear weights

### Reliability
- **Low Cognitive Load**: Simple 5-point scales (not 10-point or 100-point)
- **Clear Criteria**: Each criterion has explicit description
- **Auto-save**: Prevents data loss during evaluation

### Validity
- **Criterion Alignment**: Scores directly map to PROMPT.md requirements
- **Weighted Formula**: Reflects actual importance of design elements
- **Absolute Assessment**: Evaluator compares to criteria, not to other pages

## Technical Details

- **Framework**: Vanilla JavaScript (no external dependencies)
- **Storage**: localStorage for session persistence
- **Design**: Swiss International Typographic Style (matching evaluated pages)
- **Browser Support**: Modern browsers (Chrome, Firefox, Safari, Edge)

## Troubleshooting

**Problem**: Progress not saving  
**Solution**: Ensure browser allows localStorage. Try using a local server (`python -m http.server`)

**Problem**: Iframe not loading pages  
**Solution**: Check that `../pages/` directory contains the original HTML files with model-specific names (web_*.html)

**Problem**: Want to re-randomize order  
**Solution**: Click "Reset All Evaluations" button at bottom of page

## Credits

Designed according to RFC 2119 specifications and experimental design best practices from psychometrics and UX research methodologies.
