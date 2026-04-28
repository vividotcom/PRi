# Sequential Evaluation Workflow - Updated Implementation

## Overview
The evaluation module now follows a strict **sequential, step-by-step workflow** where each phase becomes available only after the previous one is completed and evaluated.

## Workflow Steps

### Step 1: OI (Offres Initiales) - Initial Offers
**Only OI tab is visible initially**

1. Enter all companies and their initial offer amounts
2. Click **"Évaluer OI"** button
3. Results appear showing:
   - **À Relancer (Green)**: Companies kept for next phase
     - Top 3 companies, or
     - 4th company if gap < 15%
   - **À Écarter (Red)**: Companies discarded with reasons
     - Gap > 15%

4. After evaluation, button "**Évaluer les OA1**" appears in results section

---

### Step 2: OA2 (Offres Améliorées 1) - Improved Offers 1
**OA1 tab appears automatically after clicking "Évaluer les OA1"**

1. Companies kept from OI automatically populate OA1 tab
2. Company names are **read-only** (already selected from OI)
3. Enter **new amounts** for OA1 offers
4. Click **"Évaluer OA1"** button
5. Results appear showing:
   - **À Relancer (Green)**: Companies kept
     - Cheapest in OA1, OR
     - Cheapest from OI (ALWAYS kept even if gap > 5%), OR
     - Others with gap < 5%
   - **À Écarter (Red)**: Companies discarded
     - Gap > 5% (unless they were cheapest in OI)

6. After evaluation, button "**Évaluer les OA2**" appears

---

### Step 3: OA2 (Offres Améliorées 2) - Improved Offers 2
**OA2 tab appears automatically after clicking "Évaluer les OA2"**

1. Companies kept from OA1 automatically populate OA2 tab
2. Company names are **read-only** (selected from OA1)
3. Enter **final amounts** for OA2 offers
4. Click **"Évaluer OA2"** button
5. Final results appear showing:
   - **À Relancer pour OA3 (Green)**: Cheapest company wins
     - Proceeds to negotiation (OA3)
   - **À Écarter (Red)**: All other companies eliminated

---

## Key Logic Implementation

### OI Evaluation Logic
```
Sort by amount (ascending)
Keep: Top 3 + any 4th if (gap < 15%)
Discard: All others with gap ≥ 15%
```

### OA1 Evaluation Logic
```
Sort by amount (ascending)
Keep: 
  - Cheapest in OA1
  - ALWAYS cheapest from OI (reference price)
  - Others with gap < 5%
Discard: All others with gap ≥ 5%
```

### OA2 Evaluation Logic
```
Sort by amount (ascending)
Keep: Only cheapest (winner)
  - If tie: both kept, cheapest displayed first
Discard: All others
```

## Visual Design Features

- **Color-coded results**:
  - Green gradient cards = "À Relancer" (kept)
  - Red gradient cards = "À Écarter" (discarded)
  
- **Clear justifications**:
  - Each company shows WHY they were kept or discarded
  - Amount and gap percentage displayed
  - Strikethrough text for discarded companies

- **Sequential tabs**:
  - OI visible immediately
  - OA1 tab hidden until OI evaluated
  - OA2 tab hidden until OA1 evaluated

- **Auto-populated data**:
  - Kept companies automatically transferred to next phase
  - Company names read-only in OA1/OA2
  - Empty amount fields highlighted in yellow for data entry

## Usage Flow Diagram

```
┌─────────────────────────────────────┐
│  Start: Only OI Tab Visible         │
│  - Add companies & amounts          │
│  - Click "Évaluer OI"               │
└────────────┬────────────────────────┘
             │
             ↓
   ┌─────────────────────────────┐
   │  OI Results Displayed       │
   │  - Green: To Keep           │
   │  - Red: To Discard          │
   │  - Button: "Évaluer les OA1"│
   └────────────┬────────────────┘
                │
                ↓
   ┌──────────────────────────────────┐
   │  OA1 Tab Now Visible             │
   │  - Companies from OI auto-filled  │
   │  - Enter OA1 amounts             │
   │  - Click "Évaluer OA1"           │
   └────────────┬─────────────────────┘
                │
                ↓
   ┌──────────────────────────────────┐
   │  OA1 Results Displayed           │
   │  - Green: To Keep                │
   │  - Red: To Discard               │
   │  - Button: "Évaluer les OA2"     │
   └────────────┬─────────────────────┘
                │
                ↓
   ┌──────────────────────────────────┐
   │  OA2 Tab Now Visible             │
   │  - Companies from OA1 auto-filled │
   │  - Enter OA2 amounts             │
   │  - Click "Évaluer OA2"           │
   └────────────┬─────────────────────┘
                │
                ↓
   ┌──────────────────────────────────┐
   │  Final Results: Winner Selected   │
   │  - Green: Final winner → OA3     │
   │  - Red: Eliminated companies     │
   │  - Ready to export to Excel      │
   └──────────────────────────────────┘
```

## File Changes

1. **index.html**: 
   - OA1 and OA2 tabs hidden initially with `display:none` and `id="tabOA1"`, `id="tabOA2"`
   - Next button text updated dynamically

2. **app.js**:
   - `switchPhase()`: Simplified to not show all tabs
   - `moveToNextPhase()`: New async function that shows next tab and switches
   - `calculatePhase()`: Updates next button text based on current phase
   - Tab visibility controlled by JavaScript after evaluation

This ensures users follow the procurement evaluation process step-by-step with clear guidance at each stage.
