# Financial Evaluation Module - Phase 2 Enhancements

## Overview
Enhanced the evaluation module with visual color-coding, automatic phase progression, and intelligent company carryover between phases.

## Key Features Added

### 1. Color-Coded Results Display
- **À Relancer (Kept)**: Green boxes (#E8F5E9 background, #4CAF50 left border)
  - Shows each company's reason for being kept
  - Examples:
    - OI: "Top 3" or "Écart < 15% (X.X%)"
    - OA1: "Moins disante OA1", "Écart < 5% (X.X%)", or "Maintenue d'OI"
    - OA2: "Relancer pour OA3 (FINAL moins disante)"

- **À Écarter (Discarded)**: Red boxes (#FFEBEE background, #F44336 left border)
  - Shows reason for rejection based on phase logic
  - Examples:
    - OI: "Écart > 15% (classement 5+)"
    - OA1: "Écart > 5% (X.X%) - Non compétitif"
    - OA2: "Non retenu (pas le prix minimum)"

### 2. Automatic Company Carryover
When switching to the next phase (OI → OA1 or OA1 → OA2):
- Only companies marked as "À Relancer" are automatically imported
- Companies appear with 0 amount (highlighted in light yellow)
- Blue info banner confirms automatic import
- Company names are read-only (can't be changed in OA1/OA2)
- User enters new quoted amounts for each kept company

### 3. Smart Phase Progression
- Each phase shows only the companies that survived the previous phase
- No need to re-enter kept company names - they carry forward automatically
- Results are stored after each evaluation and referenced for next phase
- Clear visual distinction between auto-populated (greyed out) and new data entry rows

### 4. Enhanced Visual Feedback
- Tab highlighting shows active phase
- Phase banner informs users about auto-populated companies
- Empty amount fields highlighted in yellow (encourage data entry)
- Company rows with amounts entered display normally
- Gap percentages calculated dynamically based on cheapest offer in each phase

## Technical Implementation

### Backend (Flask)
- Calculation functions already implement exact procurement logic:
  - OI: Keep top 3 + 4th if gap < 15%
  - OA1: Keep cheapest OA1 + always keep OI cheapest + gap < 5%
  - OA2: Keep only cheapest (final winner)
- Results stored with company rankings and gap percentages

### Frontend (JavaScript)
- `switchPhase(phase)`: Now async, auto-populates kept companies from previous phase
- `renderPhaseTable()`: 
  - Shows auto-populated rows with grey background
  - Highlights empty amounts in yellow
  - Makes company names read-only in OA1/OA2
  - Shows phase banner for imported companies
- `calculatePhase()`: 
  - Displays results in color-coded boxes
  - Shows reason for each decision
  - Displays amount and gap percentage
  - Provides "Continue to Next Phase" button

### Frontend (HTML)
- Added `phaseBanner` div for informing users about auto-populated data
- Result sections with color-coded styling for kept/discarded companies
- Clear visual hierarchy with green/red color scheme

## User Workflow

1. **OI Phase**:
   - Enter companies and amounts
   - Click "Évaluer OI"
   - See color-coded results with reasons
   - Click "Continuer vers Phase Suivante"

2. **OA1 Phase**:
   - Companies from OI automatically imported (read-only names, 0 amounts)
   - Yellow highlighted amount fields prompt for data entry
   - Enter OA1 quoted prices
   - Click "Évaluer OA1"
   - See updated results based on OA1 logic (may exclude some from OI)
   - Click "Continuer vers Phase Suivante"

3. **OA2 Phase**:
   - Companies from OA1 automatically imported
   - Enter OA2 final prices
   - Click "Évaluer OA2"
   - See final results - one company marked as "FINAL moins disante"
   - Export to Excel or save for negotiation

## Files Modified
- `flask_app/static/js/app.js`: Enhanced switchPhase, renderPhaseTable, calculatePhase
- `flask_app/templates/index.html`: Added phase banner, improved styling
