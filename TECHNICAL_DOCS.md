# Technical Documentation

Detailed technical reference for the Rhea Job Costing tool.

---

## Architecture Overview

```
QuickBooks Export (Week 1 + Week 2 .xlsx files)
        ↓
    app.py (Flask routes)
        ↓
    job_costing_converter.py
        ├── detect_overtime_and_prepare_selection() → Phase 1: OT detection
        ├── process_paychex_files() → Phase 2: Full processing
        └── generate_job_cost_allocation_output() → Excel output
        ↓
    employee_master.py
        ├── validate_employees_against_paychex() → Roster validation
        ├── is_employee_salaried() → OT eligibility check
        └── get_employee_rate() → Rate lookup with salaried adjustment
        ↓
    paychex_parser.py
        └── parse_paychex_file() → Parse Paychex .xls for validation
        ↓
    reconciliation.py
        └── reconcile_employee() → Compare calculated vs Paychex wages
        ↓
    Excel Output (Job Cost Allocation sheet)
```

---

## Processing Logic

### Step 1: Parse Duration to Decimal Hours

**Input:** `HH:MM` (e.g., "03:30")
**Output:** Decimal hours (e.g., 3.5)

```
decimal_hours = hours + (minutes / 60)
```

Examples:
- `01:30` → 1.5 hours
- `08:15` → 8.25 hours

### Step 2: Identify Employee Names

QuickBooks format uses employee names as header rows (first column has name, Activity date is empty). The tool scans for these patterns.

### Step 3: Calculate Weekly Hours

```
Week 1 Total = Sum of all hours in Week 1 for that employee
Week 2 Total = Sum of all hours in Week 2 for that employee
```

### Step 4: Determine Overtime

- **Hourly employees:** If weekly hours > 40 → overtime
- **Salaried employees:** No overtime, but rate adjusts if >80 hours/pay period

### Step 5: OT Allocation (Hourly Only)

User selects ONE job to receive all overtime hours for that week.

**Job Key Format:**
```
"employee|week|date|customer|hours"
Example: "Andrew B. Shaw|2|09/22/2025|GAI Consultants|10.0"
```

### Step 6: Cost Calculations

**Regular Cost:**
```
Regular Cost = Regular Hours × Hourly Rate
```

**Overtime Cost:**
```
OT Cost = OT Hours × Hourly Rate × 1.5
```

**Salaried Rate Adjustment (>80 hours):**
```
Adjusted Rate = (base_rate × 80) / actual_hours
```

### Step 7: Penny-Perfect Precision

For salaried employees with >80 hours, the tool uses Python's `Decimal` module to ensure job entry amounts sum EXACTLY to `base_rate × 80`. The last job entry absorbs any remaining cents.

---

## API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Main web interface |
| `/upload` | POST | Upload files, returns OT selection data if needed |
| `/process_with_ot_selections` | POST | Complete processing with OT allocations |
| `/download/<filename>` | GET | Download generated Excel file |
| `/api/roster` | GET/POST | Get/Add employees |
| `/api/roster/update` | PUT | Update employee |
| `/api/roster/delete` | POST | Delete employee |
| `/api/roster/bulk` | POST | Bulk update employees |

---

## Data Structures

### Employee Master (employees.json)

```json
{
  "last_updated": "2025-12-08T10:00:00",
  "employees": [
    {
      "name": "Marcella J. Gallick",
      "employee_type": "salaried",
      "base_rate": 67.36,
      "qb_indirect_code": "Y - Indirect Employee Labor:MG",
      "qb_direct_code": "Y - Direct Employee Labor:PM II",
      "paychex_name": "Gallick, Marcella"
    }
  ]
}
```

### OT Allocation Format

```javascript
// Key: "employee_week", Value: job_key
{"Derek J. Horneman_1": "Derek J. Horneman|1|09/15/2025|GAI Consultants|8.0"}
```

---

## Two-Phase Processing

When overtime is detected for hourly employees:

1. **Phase 1** (`detect_overtime_and_prepare_selection`): Analyzes files, returns OT situations requiring user input
2. **Phase 2** (`process_paychex_files` with `ot_allocations`): Processes with user's job selections

---

## Employee Totals Display

**Column Order:**
`Employee_Name → Regular_Hours → OT_Hours → Total_Hours → Base_Rate → Adjusted_Rate → OT_Rate → Total_Cost`

**Conditional Columns:**
- `Adjusted_Rate`: Shows only for salaried employees with >80 hours
- `OT_Rate`: Shows only for hourly employees with OT hours

---

## Validation Checklist

After processing, verify:

1. **Weekly totals** match QuickBooks summaries
2. **OT only appears** for hourly employees with >40 hours/week
3. **Total Hours** = Regular + OT for each employee
4. **Cost calculations** use correct rates and 1.5× multiplier

---

## Known Limitations

- Session storage is in-memory (not persisted across restarts)
- SECRET_KEY is hardcoded (needs environment variable for production)
- Employee name matching is exact (case-sensitive, whitespace-sensitive)

---

## Implementation History

### December 2025 Changes

1. **Fixed OT calculation bug** - OT hours were showing 0.00 due to index mismatch
2. **Added job_key system** - Stable content-based identifiers for job matching
3. **New modules** - `paychex_parser.py` and `reconciliation.py` for Paychex validation
4. **Fixed Employee Totals display** - Explicit column ordering, fixed $NaN display
5. **Penny-perfect precision** - `Decimal` module for salaried employee calculations

### December 8, 2024 Implementation

1. **Employee Master System** - `employee_master.py` with salaried/hourly detection
2. **Adjusted Rate Formula** - `(base_rate × 80) / actual_hours` for salaried
3. **Skip OT for Salaried** - Only hourly employees trigger OT allocation UI
4. **Simplified OT Selection** - Single dropdown instead of distributed hours

---

## Federal Compliance Notes

- **40-hour threshold** is federal standard for hourly employees
- **1.5× multiplier** is federal minimum for overtime
- **Audit trail** preserved in "Detailed Records" sheet
- Tool designed for government contract compliance

---

**Last Updated:** December 2025
