# Rhea Job Costing Tool - Implementation Notes (Dec 8, 2024)

## What Was Implemented

Based on client feedback from December 5th meeting with Lynn & Marcy:

### 1. Employee Master System
- **New file:** `employee_master.py` - handles salaried/hourly detection and rate calculations
- **New file:** `employees.json` - pre-populated with 22 employees from client spreadsheet
- 8 salaried employees, 14 hourly employees

### 2. Adjusted Rate Formula for Salaried Employees
Formula: `(base_rate × 80) / actual_hours`
- Example: Marcy at $67.36/hr working 95 hours → $56.72/hr adjusted
- Verified against client's existing spreadsheet calculations

### 3. Skip OT Prompts for Salaried
- Modified `detect_overtime_and_prepare_selection()` in `job_costing_converter.py`
- Only hourly employees with >40 hrs/week trigger OT allocation UI

### 4. New Web UI Workflow
- Step 1: Review/approve employee roster (editable rates)
- Step 2: Upload QuickBooks Week 1 + Week 2 files
- Step 3: Results with download

### 5. Simplified OT Selection
- Changed from distributing hours across multiple inputs to single dropdown
- User picks ONE job to receive all OT hours

## Files Changed
- `employee_master.py` (NEW)
- `employees.json` (NEW)
- `job_costing_converter.py` (MODIFIED - significant changes)
- `app.py` (MODIFIED - added API endpoints)
- `templates/index.html` (MODIFIED - complete UI overhaul)

## Known Issues / Needs Testing
- The full integration needs testing with real QuickBooks export files
- Some code paths may have bugs introduced during the refactor
- The OT allocation format changed from `{key: {index: hours}}` to `{key: index}`

## Key Data Structures

### Employee Master (employees.json)
```json
{
  "employees": [
    {
      "name": "Marcella J. Gallick",
      "employee_type": "salaried",
      "base_rate": 67.36,
      "qb_indirect_code": "Y - Indirect Employee Labor:MG",
      "qb_direct_code": "Y - Direct Employee Labor:PM II"
    }
  ]
}
```

### OT Allocation (new format)
```javascript
// Old format (distributed):
{"Amy C. Brown_1": {5: 0.3, 12: 0.2}}

// New format (single job selection):
{"Derek J. Horneman_1": 5}  // All OT goes to job at index 5
```

## Client Requirements Reference
1. Skip OT for salaried ✓
2. Master employee file with roster approval ✓
3. Adjusted rate calculation ✓
4. Summary column for QuickBooks ✓
5. Week 1/Week 2 files come from QuickBooks (not Paychex) - terminology updated ✓

## Next Steps for Debugging
1. Start Flask app: `python3 app.py`
2. Test roster loading at http://localhost:5000
3. Test file upload with sample QuickBooks exports
4. Verify OT allocation works for hourly employees
5. Check Excel output has correct columns and calculations
