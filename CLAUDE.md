# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rhea Job Costing is a web-based automation tool that converts QuickBooks payroll exports into job costing summaries for Rhea Engineering. It replaces a manual 6-8 hour bi-weekly process with an automated 30-minute workflow.

**Business Context:** This tool is used for federal audit compliance, requiring accurate tracking of regular vs. overtime hours and proper cost allocation across government contracts.

## Development Commands

### Start Development Server
```bash
./start_webapp.sh
# Or manually:
source venv/bin/activate
python app.py
```
Server runs at http://127.0.0.1:5000

### Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run Command-Line Processing
```bash
python job_costing_converter.py week1.xlsx week2.xlsx output.xlsx
```

### Stop Server
```bash
# If running in foreground: Ctrl+C
# If port in use:
lsof -ti:5000 | xargs kill -9
```

## Architecture

### Core Processing Pipeline

```
QuickBooks Export (Week 1 + Week 2 .xlsx files)
        ↓
    app.py (Flask routes)
        ↓
    job_costing_converter.py
        ├── detect_overtime_and_prepare_selection() → Phase 1: OT detection
        ├── process_paychex_files() → Phase 2: Full processing
        └── generate_job_cost_allocation_output() → Single-sheet output with reconciliation
        ↓
    employee_master.py
        ├── validate_employees_against_paychex() → Roster validation
        ├── is_employee_salaried() → OT eligibility check
        └── get_employee_rate() → Rate lookup with salaried adjustment
        ↓
    paychex_parser.py (NEW)
        └── parse_paychex_file() → Parse Paychex payroll .xls for validation
        ↓
    reconciliation.py (NEW)
        └── reconcile_employee() → Compare calculated vs Paychex wages
        ↓
    Excel Output (Job Cost Allocation sheet with reconciliation rows)
```

### Key Processing Logic

1. **Employee Detection**: Parses QuickBooks format where employee names appear as header rows (first column has name, Activity date is empty)
2. **Overtime Calculation**:
   - Hourly employees: OT for hours >40/week, triggers UI for job selection
   - Salaried employees: No OT, rate adjusted using formula `(base_rate × 80) / actual_hours`
3. **OT Allocation**: User selects which single job receives all OT hours (changed from proportional distribution)

### Data Flow

- **employees.json**: Master roster with employee types and rates (persisted)
- **temp_storage dict**: In-memory session storage for multi-step OT allocation workflow
- **UPLOAD_FOLDER**: Temp directory for uploaded files (cleaned after processing)

### Two-Phase Processing

When overtime is detected for hourly employees:
1. **Phase 1** (`detect_overtime_and_prepare_selection`): Returns OT situations requiring user input
2. **Phase 2** (`process_paychex_files` with `ot_allocations`): Processes with user selections

## API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Main web interface |
| `/upload` | POST | Upload Week 1 + Week 2 files, returns OT selection data if needed |
| `/process_with_ot_selections` | POST | Complete processing with OT allocations |
| `/download/<filename>` | GET | Download generated Excel file |
| `/api/roster` | GET/POST | Get all employees / Add new employee |
| `/api/roster/update` | PUT | Update existing employee |
| `/api/roster/delete` | POST | Delete employee |
| `/api/roster/bulk` | POST | Bulk update employees |

## File Format

QuickBooks exports must have these columns (after 4 header rows skipped):
- `Activity date`
- `Customer full name`
- `Duration` (HH:MM format)
- `Rates`
- `Description`
- `Billable` (Y/N)

## Key Business Rules

1. **40-hour OT threshold** is federal standard for hourly employees
2. **1.5× multiplier** for overtime hours
3. **Salaried rate adjustment**: When salaried employees work >80 hours/pay period, their effective rate decreases to maintain fixed salary total
4. **OT allocation format**: `{employee_week: job_key}` - uses stable content-based keys instead of indices
5. **Penny-perfect totals**: For salaried employees with >80 hours, job entry amounts are calculated using Python's `Decimal` module to ensure they sum EXACTLY to `base_rate × 80` (the correct salary). The last job entry absorbs any remaining cents ("plug" adjustment) to guarantee penny-perfect reconciliation. This works with or without Paychex data.

## OT Allocation Technical Details

The OT allocation uses a **job_key** system to match jobs between Phase 1 (detection) and Phase 2 (processing):

```python
# Job key format: "employee|week|date|customer|hours"
# Example: "Andrew B. Shaw|2|09/22/2025|GAI Consultants|10.0"
```

This was implemented to fix an index mismatch bug where dataframe indices changed after merge operations.

## Employee Totals Display

**Column order** (explicit in `TOTALS_COLUMN_ORDER` constant, `index.html:1927`):
`Employee_Name → Regular_Hours → OT_Hours → Total_Hours → Payrolled_Hours → Base_Rate → Adjusted_Rate → OT_Rate → Total_Cost`

**Hours columns explained**:
- `Total_Hours`: Actual hours worked (for project tracking)
- `Payrolled_Hours`: Hours that should match Paychex payroll
  - Hourly employees: Same as Total_Hours (they get paid for all hours including OT)
  - Salaried employees: Capped at 80 (they don't get OT pay - fixed salary)

**Conditional columns** (backend returns `"-"` string, not null):
- `Adjusted_Rate`: Shows value only for salaried employees with >80 hours
- `OT_Rate`: Shows value only for hourly employees with OT hours

**Hours Invariant**: `Regular_Hours + OT_Hours = Total_Hours` (enforced at line 723 of `job_costing_converter.py`)

## Known Limitations

- Session storage is in-memory (not persisted across restarts)
- SECRET_KEY is hardcoded (needs environment variable for production)
- Employee name matching is exact (case-sensitive, whitespace-sensitive)

## Recent Changes (Dec 2025)

1. **Fixed OT calculation bug**: OT hours were showing 0.00 for all employees due to index mismatch between phases
2. **Added job_key system**: Stable content-based identifiers for job matching
3. **UI improvements**: Fixed white text on tables, show all summary rows, added rate columns
4. **New modules**: `paychex_parser.py` and `reconciliation.py` for Paychex validation
5. **Fixed Employee Totals display**: Explicit column ordering (Employee_Name first), fixed $NaN display for conditional rate columns
6. **Penny-perfect precision for salaried employees**: Added `calculate_precise_salaried_amounts()` function using Python's `Decimal` module to eliminate rounding errors. Job entry amounts for salaried employees with >80 hours now sum EXACTLY to `base_rate × 80`. Works with or without Paychex file - eliminates need for manual "plug" adjustments in QuickBooks.
7. **Fixed OT hours double-counting**: Added invariant enforcement (`Regular_Hours = Hours_Decimal - OT_Hours`) to ensure OT hours are properly subtracted from regular hours. Previously, Excel output showed inflated totals because OT rows were added without reducing regular hours.
8. **Added Payrolled Hours metric**: New column showing hours that should match Paychex payroll (salaried employees capped at 80). Grand totals now show both "Actual Hours Worked" and "Payrolled Hours" with explanation of the difference (unpaid salaried OT).
9. **Added "Job Costing - By Employee" sheets**: New per-employee Excel tabs in QuickBooks Item import format for direct import into QB. Each employee gets their own sheet with columns: PRODUCT/SERVICE, DESCRIPTION, QTY, RATE, AMOUNT, CUSTOMER/PROJECT.

## Per-Employee Sheets (QuickBooks Import Format)

The Excel output now includes one tab per employee, formatted for QuickBooks Item import.

### INDIRECT vs DIRECT Classification
Projects are classified to determine which QB labor code to use:
- **INDIRECT**: Project starts with `"Rhea:80"` (overhead) OR contains `"Proposal"` (case-insensitive)
- **DIRECT**: All other projects (billable client work)

### Output Column Mapping
| Column | INDIRECT Projects | DIRECT Projects |
|--------|-------------------|-----------------|
| PRODUCT/SERVICE | `qb_indirect_code` from employees.json | `qb_direct_code` from employees.json |
| DESCRIPTION | Employee full name | Job title (parsed from qb_direct_code) |
| QTY | Hours worked | Hours worked |
| RATE | Hourly rate | Hourly rate |
| AMOUNT | QTY × RATE | QTY × RATE |
| CUSTOMER/PROJECT | Project name | Project name |

### OT Handling on Employee Sheets
- OT hours appear as separate rows with "(OT)" appended to DESCRIPTION
- OT rate is 1.5× the regular rate
- Salaried employees never have OT rows (they get rate adjustment instead)

### Helper Functions (job_costing_converter.py)
- `is_indirect_project(customer_name)`: Returns True if project is indirect
- `get_job_title_from_direct_code(qb_direct_code)`: Extracts job title from QB code
- `generate_by_employee_sheets(writer, df_work, employees_data, employee_total_hours)`: Creates all employee sheets
