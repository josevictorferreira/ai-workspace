# Quick Start Guide - Blind Evaluation System

## 🎯 What This System Does

Evaluates 26 LLM-generated Swiss-style real estate pages **without revealing which LLM created which page** until after you complete the evaluation. This eliminates bias and ensures objective scoring based on your specific 5-question scorecard.

## 🚀 Getting Started (3 Steps)

### Step 1: Open the Evaluator

**Option A - Direct Open (Recommended)**
```bash
# Simply double-click this file:
blind_evaluator/evaluator.html
```

**Option B - Local Server (If iframe doesn't load)**
```bash
cd /path/to/real-estate-page-design
python3 -m http.server 8000
# Then open: http://localhost:8000/blind_evaluator/evaluator.html
```

### Step 2: Score Each Page

You'll see:
- **Left Panel**: Preview of the real estate page with "View Source" and "Open in New Tab" buttons
- **Right Panel**: The 5-question scorecard

For each page:
1. Review the design (use "Open in New Tab" for full-screen)
2. Answer all 5 questions
3. Add optional notes
4. Click "Next →" (auto-saves)

**Time Budget**: 3-4 minutes per page = ~90 minutes total

### Step 3: Export Results

When done:
1. Click **"Export CSV"** or **"Export JSON"**
2. Open the exported file
3. **Model identities revealed** in the `Original Filename` column

---

## 📋 The Scorecard - Your 5 Questions

### Pass/Fail Check (Binary: 0 or 1)

**Question 1: Specific Locations**
- **Ask yourself**: "Did it include the specific locations: Paraná, Londrina, and Ibiporã?"
- **Scoring**: NO = 0, YES = 1
- **Weight**: 5× (Important requirement)
- **Tip**: Look in the location filters - all three must be present

### 1-5 Rating Scales (Likert)

**Question 2: Swiss Aesthetic**
- **Ask yourself**: "DOES it feel cluttered?"
- **Scoring**:
  - 1 = Cluttered/Ugly
  - 5 = High use of negative space/Grid alignment
- **Weight**: 3×
- **What to look for**: White space, visible grid, asymmetric layout, clean typography

**Question 3: Property Cards**
- **Ask yourself**: "Would I click this on a real site?"
- **Scoring**:
  - 1 = Looks like a wireframe/broken
  - 5 = Looks like a production Zillow/Airbnb clone
- **Weight**: 3×
- **What to look for**: Professional images, clear pricing, good typography hierarchy

**Question 4: Micro-interactions**
- **Ask yourself**: "When I hover over buttons or paginators, is there visual feedback (color change/cursor change)?"
- **Scoring**:
  - 1 = Static/Dead
  - 5 = Responsive/Alive
- **Weight**: 2×
- **What to look for**: Hover states on buttons, paginator, property cards

### Image Hover Feature (Special: 0/3/5/7)

**Question 5: Image Hover Implementation**
- **Ask yourself**: 
  1. "Is it there?"
  2. "Does it work visually?"
  3. **View Source (Ctrl+U)**: "Did it use `<script>` logic to swap the image, or CSS `:hover` techniques?"

- **Scoring**:
  - **0** = Missing (feature not implemented)
  - **3** = Works poorly (glitchy, slow, broken)
  - **5** = Works well with JS (`<script>` tags used)
  - **7** = CSS only (no JavaScript, pure CSS `:hover`)

- **Weight**: 1×
- **Bonus**: CSS-only implementations get the highest score (7)

---

## 🧮 Scoring Formula

Your total score is calculated as:

```
S = (5 × C2) + (3 × L3) + (3 × L4) + (2 × L5) + (1 × W6)
```

Where:
- **C2** = Location check (0 or 1)
- **L3** = Swiss Aesthetic (1 to 5)
- **L4** = Property Cards (1 to 5)
- **L5** = Micro-interactions (1 to 5)
- **W6** = Image Hover (0, 3, 5, or 7)

**Maximum Possible Score**: 5 + 15 + 15 + 10 + 7 = **52 points**

### Why This Formula Works

1. **Penalty for Missing Locations**: If C2 = 0, model loses 5 points
2. **Emphasis on Design**: Likert scales (L3, L4, L5) worth up to 40 points total
3. **CSS Bonus**: W6 incentivizes CSS-only implementation (7 pts) over JS (5 pts)

---

## 🔒 How Blinding Works

### During Evaluation
- Pages labeled: "Evaluation Page 01", "Evaluation Page 02", etc.
- Pages presented in **random order** (shuffled on first load)
- No model names visible anywhere
- Original filenames hidden

### After Export
```csv
Evaluation Order,Blinded ID,Original Filename,Locations,Swiss,Cards,Interactions,Hover,Total Score
1,page-15.html,web_intellect_3.html,1,4,5,5,7,48
2,page-03.html,web_claude_opus_4.5.html,1,5,5,5,7,52
3,page-22.html,web_qwen_3_235b_a22b_thinking.html,0,3,4,4,5,30
```

Only in the **exported file** do you see:
- `web_claude_opus_4.5.html` → Claude Opus 4.5
- `web_gpt_5.2.html` → GPT 5.2
- etc.

---

## 🛠️ Common Operations

### Pause & Resume
Your progress auto-saves in browser localStorage. You can:
- Close the browser
- Come back later
- Scores and randomization order persist

### View Source
Click the **"View Source (Ctrl+U)"** button to:
- Inspect image hover implementation (Question 5: CSS vs JS)
- Opens the page in a new tab for code inspection

### Start Fresh
Click **"Reset All Evaluations"** at the bottom to:
- Clear all scores
- Generate new random order
- Start from scratch

### View Progress
Top progress bar shows: **"X / 26 COMPLETED"**

---

## 📁 Export Format Examples

### CSV Export (Open in Excel/Google Sheets)
```csv
Evaluation Order,Blinded ID,Original Filename,Locations,Swiss,Cards,Interactions,Hover,Total Score,Notes
1,page-15.html,web_intellect_3.html,1,4,5,5,7,48,"Excellent hover, good design"
2,page-03.html,web_claude_opus_4.5.html,1,5,5,5,7,52,"Perfect implementation"
3,page-22.html,web_qwen_3_235b_a22b_thinking.html,0,3,4,4,5,30,"Missing Ibiporã location"
```

### JSON Export (Programmatic Analysis)
```json
{
  "metadata": {
    "timestamp": "2025-12-16T21:00:00.000Z",
    "totalPages": 26,
    "completedPages": 26,
    "scoringFormula": "S = (5 × C2) + (3 × L3) + (3 × L4) + (2 × L5) + (1 × W6)"
  },
  "evaluationOrder": [
    {
      "evaluationPosition": 1,
      "blindedId": "page-15.html",
      "originalFilename": "web_intellect_3.html",
      "scores": {
        "locations": 1,
        "swiss": 4,
        "cards": 5,
        "interactions": 5,
        "hover": 7,
        "notes": "Excellent hover, good design",
        "totalScore": 48
      }
    }
  ]
}
```

---

## 🎓 Evaluation Tips

### Before You Start
1. Read `PROMPT.md` to understand Swiss design requirements
2. Have it open in another tab as reference
3. Clear 90 minutes of uninterrupted time (3-4 min per page × 26 pages)

### During Evaluation

**General Tips:**
1. **Be Consistent**: Use the same mental scale for all 26 pages
2. **Compare to Criteria**: Judge against the questions, not against other pages
3. **Use Full Scale**: Don't be afraid to give 1s or 5s
4. **Trust First Impression**: Spend 3-4 minutes max per page
5. **Take Notes**: Quick observations help maintain consistency

**Question-Specific Tips:**

**Q1 (Locations):**
- Check the location filter dropdown/section
- Must have: "Paraná" (state) AND "Londrina" AND "Ibiporã" (cities)
- All three required for YES (1)

**Q2 (Swiss Aesthetic):**
- High score (4-5): Lots of white space, visible grid, clean
- Low score (1-2): Cluttered, no breathing room, chaotic

**Q3 (Property Cards):**
- High score (4-5): Professional, polished, production-ready
- Low score (1-2): Ugly placeholders, broken layout

**Q4 (Micro-interactions):**
- Hover over buttons, paginator, cards
- High score (4-5): Color changes, smooth feedback
- Low score (1-2): Nothing happens, static

**Q5 (Image Hover):**
- Hover over property card images
- Does image change after ~1 second?
- Click "View Source" to check implementation:
  - **7 pts**: Only CSS (`:hover`, no `<script>`)
  - **5 pts**: JavaScript used (`<script>` tags present)
  - **3 pts**: Works but glitchy/slow
  - **0 pts**: No hover effect at all

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| Progress not saving | Enable localStorage in browser settings |
| Iframe blank | Use local server: `python3 -m http.server 8000` |
| Random order same every time | Click "Reset All Evaluations" to re-shuffle |
| Want to skip a page | You can, but try to score all 26 for complete data |
| Made a mistake | Navigate back with "← Previous" button |
| Can't see source | Click "View Source" button or right-click iframe → "View Frame Source" |

---

## 📈 After Evaluation

### Analyze Results
1. **Sort by Total Score**: Find top-performing LLMs
2. **Check Compliance**: How many included all three locations?
3. **Compare Criteria**: Which models excel at Swiss aesthetic vs micro-interactions?
4. **Hover Implementation**: How many used CSS-only (7 pts) vs JS (5 pts)?

### Example Analysis Questions
- Which model scored highest overall?
- How many models failed the Locations requirement?
- What's the average score for Swiss Aesthetic (Q2)?
- Did CSS-only hover implementations correlate with higher total scores?

---

## 📞 Support

For issues or questions, review:
1. `blind_evaluator/README.md` - Full technical documentation
2. `plans/blind-evaluation-framework.md` - Implementation details
3. `PROMPT.md` - Design specification reference

**Scoring Formula**: S = (5 × C2) + (3 × L3) + (3 × L4) + (2 × L5) + (1 × W6)  
**Maximum Score**: 52 points  
**Total Pages**: 26  
**Questions**: 5  
**Time**: 3-4 minutes per page

**Last Updated**: 2025-12-16  
**Version**: 3.0.0 (5-Question Scorecard - Single File Question Removed)
