# Financial Evaluation Module - User Guide

## Overview
The Financial Evaluation Module allows you to compare supplier offers across three phases (OI, OA1, OA2) with automatic calculation logic and Excel export capability.

## How to Access
Click the **"Évaluations"** button in the navbar (next to "Délais" and before "Importer").

## Workflow

### 1. Create a New Evaluation
1. Click **"+ Nouvelle Évaluation"** in the left panel
2. Enter a title (e.g., "Évaluation Prestation Maintenance")
3. Click **OK**

### 2. Phase 1: OI (Offres Initiales)
1. Under the **OI** tab, enter company data:
   - Company name (e.g., "Prestataire 1")
   - Amount/Price
2. Click **"+ Ajouter"** to add more companies (up to 4+)
3. Click **"Évaluer OI"** to calculate results

**OI Logic:**
- Sorts by price (cheapest first)
- Keeps top 3 companies
- Includes 4th company if price gap < 15% from cheapest

**Results show:**
- "À Relancer" - Companies to keep for OA1
- "À Écarter" - Companies discarded

### 3. Phase 2: OA1 (Offres Améliorées 1)
1. Switch to **OA1** tab
2. Enter improved offers from each company
3. Click **"Évaluer OA1"** to calculate

**OA1 Logic:**
- Keeps cheapest OA1 offer
- **ALWAYS includes** the cheapest company from OI (even if gap > 5%)
- Includes others with gap < 5% from cheapest OA1

### 4. Phase 3: OA2 (Offres Améliorées 2)
1. Switch to **OA2** tab
2. Enter final offers from companies
3. Click **"Évaluer OA2"** to calculate

**OA2 Logic:**
- Keeps only the cheapest offer (FINAL winner)
- If tie, both marked but cheapest is winner
- Marked as "Relancer pour OA3 (FINAL moin disante)"

## Features

### Edit Company Data
- Click directly in company name or amount fields to edit
- Changes auto-save

### Delete Entries
- Click the trash icon to remove a company from the evaluation

### Save Title
- Update evaluation title anytime with the **"Enregistrer"** button

### Export to Excel
- Click **"Exporter Excel"** to download complete evaluation
- File includes all phases with calculations and classifications
- Name: `Evaluation_[Title].xlsx`

### Delete Evaluation
- Click **"Supprimer"** to delete entire evaluation (with confirmation)

## Data Persistence
- All evaluations are saved to database automatically
- Evaluations persist across sessions
- Can reload previous evaluations from the list

## Tips
- Evaluations don't require PR linking (can be standalone)
- Use descriptive titles like "Eval_Prestation_[Name]_[Date]"
- Export each phase separately if needed
- Results update in real-time after calculation

## Technical Details
- Database: SQLite (tables: financial_evaluation, evaluation_entry)
- Export format: .xlsx (Excel compatible)
- Phase data retained through all 3 phases
- No data loss when moving between phases
