import pandas as pd
import numpy as np
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import sys
import json
from employee_master import (
    is_employee_salaried, get_employee_rate, validate_employees_against_paychex,
    get_paychex_name_aliases, load_employees
)
from paychex_parser import parse_paychex_file, match_employees, PaychexEmployee
from reconciliation import (
    reconcile_employee, generate_reconciliation_report, format_status_emoji,
    format_rate_note, get_reconciliation_summary, ReconciliationReport
)

def parse_duration_to_hours(duration_str):
    """
    Convert HH:MM duration format to decimal hours
    Example: '03:30' -> 3.5
    """
    if pd.isna(duration_str) or duration_str == '':
        return 0.0
    
    try:
        # Handle both 'HH:MM' and just 'H:MM' formats
        parts = str(duration_str).split(':')
        hours = int(parts[0])
        minutes = int(parts[1]) if len(parts) > 1 else 0
        return hours + (minutes / 60.0)
    except:
        return 0.0

def determine_week_number(date_str, pay_period_start):
    """
    Determine if a date is in week 1 or week 2 of the pay period
    """
    try:
        date = pd.to_datetime(date_str)
        days_diff = (date - pay_period_start).days
        return 1 if days_diff < 7 else 2
    except:
        return 1

def create_job_key(employee_name, week, activity_date, customer, hours):
    """
    Create a unique, stable identifier for a job entry.

    This key is used to match jobs between Phase 1 (OT detection) and Phase 2 (processing).
    Unlike dataframe indices which change during concat/merge operations, this key
    is based on the actual data values and remains stable.

    Parameters:
    - employee_name: Employee's full name
    - week: Week number (1 or 2)
    - activity_date: Date of the work activity
    - customer: Customer/job full name
    - hours: Hours worked (rounded to 4 decimals for consistency)

    Returns:
    - A pipe-delimited string that uniquely identifies this job entry
    """
    emp = str(employee_name).strip()
    wk = int(week)
    date = str(activity_date).strip()
    cust = str(customer).strip()
    hrs = round(float(hours), 4)
    return f"{emp}|{wk}|{date}|{cust}|{hrs}"


def calculate_precise_salaried_amounts(
    emp_summary: pd.DataFrame,
    base_rate: float,
    total_hours: float,
    paychex_gross_wages: float = None
) -> tuple:
    """
    Calculate job entry amounts for salaried employees that sum to the exact total.

    For salaried employees, the TOTAL compensation is fixed: base_rate × 80 hours.
    This function distributes that exact amount across job entries using precise
    Decimal arithmetic, ensuring the sum is penny-perfect.

    Works in TWO modes:
    1. WITHOUT Paychex: Uses base_rate × 80 as the target total (mathematically correct)
    2. WITH Paychex: Uses Paychex gross_wages as target (validates against actual payment)

    If Paychex is provided and differs from base_rate × 80 by more than $0.05,
    this indicates a data issue that should be flagged (not silently masked).

    The last entry absorbs any remaining cents via "plug" or "penny reconciliation"
    (standard accounting practice). This eliminates manual rate adjustments.

    Args:
        emp_summary: DataFrame with job entries, must have 'Customer full name'
                     and 'Regular_Hours' columns
        base_rate: Employee's base hourly rate from employees.json
        total_hours: Total hours worked by employee in pay period
        paychex_gross_wages: Optional - actual payment from Paychex for verification

    Returns:
        tuple: (amounts_dict, precise_rate, target_total, source)
            - amounts_dict: {customer_name: adjusted_amount} for each job
            - precise_rate: The rate used (target / hours), NOT rounded
            - target_total: The total being distributed
            - source: 'calculated' or 'paychex' indicating which total was used

    Example:
        Ferguson: base_rate $40.66, 81 hours
        - Calculated total: 40.66 × 80 = $3,252.80
        - Precise rate: 3252.80 / 81 = 40.158024691358...
        - Each job gets hours × rate, rounded to cents
        - Last job gets remaining amount to hit $3,252.80 exactly
    """
    # Calculate the expected total for salaried employee: base_rate × 80
    calculated_total = Decimal(str(base_rate)) * Decimal('80')
    # Round to cents (this IS the exact salary)
    calculated_total = calculated_total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    # Determine which total to use
    if paychex_gross_wages is not None:
        paychex_total = Decimal(str(paychex_gross_wages))
        difference = abs(calculated_total - paychex_total)

        # If Paychex matches calculated (within $0.01), use calculated (more traceable)
        # If significant difference, use Paychex but this indicates a potential issue
        if difference <= Decimal('0.01'):
            target = calculated_total
            source = 'calculated'
        else:
            # Use Paychex but note this for reconciliation
            target = paychex_total
            source = 'paychex'
    else:
        target = calculated_total
        source = 'calculated'

    hours = Decimal(str(total_hours))

    # Calculate the precise rate (NOT rounded - full precision)
    precise_rate = target / hours

    # Calculate amounts for each job entry
    amounts = {}
    running_total = Decimal('0')
    customers = list(emp_summary['Customer full name'])

    for i, customer in enumerate(customers):
        row = emp_summary[emp_summary['Customer full name'] == customer].iloc[0]
        job_hours = Decimal(str(row['Regular_Hours']))

        if i == len(customers) - 1:
            # Last entry: assign remaining amount for penny-perfect total
            amount = target - running_total
        else:
            # Calculate and round to 2 decimals (cents)
            amount = (job_hours * precise_rate).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

        amounts[customer] = float(amount)
        running_total += Decimal(str(amounts[customer]))

    return amounts, float(precise_rate), float(target), source


def generate_job_cost_allocation_output(
    df_work: pd.DataFrame,
    paychex_match_results: dict = None,
    reconciliation_report: ReconciliationReport = None,
    output_file: str = 'job_cost_allocation.xlsx'
) -> dict:
    """
    Generate the single-sheet Job Cost Allocation output with reconciliation rows.

    This matches the format from job_cost_allocation_sep28.xlsx:
    - Employee line items with: Employee Name, Project/Job Code, Hours, Rate, Amount, Rate Type, Notes
    - After each employee's items: Reconciliation rows showing Calculated vs Paychex totals

    Args:
        df_work: DataFrame with processed work data
        paychex_match_results: Dict mapping QB employee name -> PaychexEmployee (or None)
        reconciliation_report: ReconciliationReport with reconciliation results
        output_file: Path for output Excel file

    Returns:
        Dict with output summary and reconciliation data
    """
    if paychex_match_results is None:
        paychex_match_results = {}

    # Get employee rate info for base/adjusted rate display
    employees_data = load_employees()

    # Calculate total hours per employee for rate adjustment calculation
    employee_total_hours = df_work.groupby('Employee_Name')['Hours_Decimal'].sum().to_dict()

    # Build the output rows
    output_rows = []

    # Sort employees alphabetically for consistent output
    sorted_employees = sorted(df_work['Employee_Name'].unique())

    for emp_name in sorted_employees:
        emp_data = df_work[df_work['Employee_Name'] == emp_name].copy()

        # Get employee info
        is_salaried = is_employee_salaried(emp_name)
        total_hours = employee_total_hours.get(emp_name, 80.0)
        rate, base_rate, is_adjusted = get_employee_rate(emp_name, total_hours)

        # Check for Paychex data (for verification and optional precision source)
        paychex_emp = paychex_match_results.get(emp_name) if paychex_match_results else None

        # Determine if this is a salaried employee with adjusted rate (>80 hours)
        # These employees need precise amount calculations to avoid rounding errors
        use_precise_calculation = is_salaried and is_adjusted

        # Determine rate type and notes for this employee
        # Target format: Only show hours note for salaried employees working >80 hours
        if is_salaried and is_adjusted:
            rate_type = 'Adjusted'
            rate_note_base = f"{total_hours:.1f}hrs total"  # Simplified format matching target
        elif is_salaried:
            rate_type = 'Base'
            rate_note_base = ""  # No note for standard 80-hour salaried (target shows NaN)
        else:
            rate_type = 'Base'
            rate_note_base = ""  # No note for hourly employees on regular rows

        # Group by customer/project for this employee
        emp_summary = emp_data.groupby('Customer full name').agg({
            'Hours_Decimal': 'sum',
            'Regular_Hours': 'sum',
            'OT_Hours': 'sum',
            'Regular_Cost': 'sum',
            'OT_Cost': 'sum',
            'Total_Cost': 'sum',
            'Hourly_Rate': 'first'
        }).reset_index()

        # Calculate precise amounts for salaried employees with >80 hours
        # This ensures job entry amounts sum EXACTLY to base_rate × 80 (the correct salary)
        # Works with OR without Paychex data - no more $0.002 discrepancies
        precise_amounts = None
        display_rate = rate
        target_total = None
        amount_source = None

        if use_precise_calculation:
            paychex_wages = paychex_emp.gross_wages if paychex_emp else None
            precise_amounts, display_rate, target_total, amount_source = calculate_precise_salaried_amounts(
                emp_summary, base_rate, total_hours, paychex_wages
            )

        emp_calculated_total = 0.0
        first_row = True

        for _, row in emp_summary.iterrows():
            customer = row['Customer full name']
            regular_hours = row['Regular_Hours']
            ot_hours = row['OT_Hours']
            regular_cost = row['Regular_Cost']
            ot_cost = row['OT_Cost']
            hourly_rate = row['Hourly_Rate']

            # Add regular hours row
            if regular_hours > 0:
                # Determine amount: use precise calculation for salaried w/>80hrs, else original
                if use_precise_calculation and precise_amounts:
                    # Precise amount ensures sum equals exactly base_rate × 80 (or Paychex if provided)
                    amount_value = precise_amounts.get(customer, round(regular_cost, 2))
                    # Use 6 decimal places to show precise rate (reveals full precision)
                    rate_value = round(display_rate, 6)
                else:
                    # Original calculation (formula-based rate) for hourly or salaried ≤80hrs
                    amount_value = round(regular_cost, 2)
                    rate_value = round(hourly_rate, 4) if rate_type == 'Adjusted' else round(hourly_rate, 2)

                # Use None for empty notes (proper Excel null), only show note on first row if it has content
                notes_value = rate_note_base if (first_row and rate_note_base) else None
                output_rows.append({
                    'Employee Name': emp_name,
                    'Project/Job Code': customer,
                    'Hours': round(regular_hours, 2),
                    'Rate': rate_value,
                    'Amount': amount_value,
                    'Rate Type': rate_type,
                    'Notes': notes_value
                })
                emp_calculated_total += amount_value
                first_row = False

            # Add OT hours row (separate line item)
            # Note: Salaried employees don't get OT rows (is_employee_salaried check happens earlier)
            if ot_hours > 0:
                ot_rate = hourly_rate * 1.5
                output_rows.append({
                    'Employee Name': emp_name,
                    'Project/Job Code': customer,
                    'Hours': round(ot_hours, 2),
                    'Rate': round(ot_rate, 2),
                    'Amount': round(ot_cost, 2),
                    'Rate Type': 'OT 1.5x',
                    'Notes': 'Overtime'
                })
                emp_calculated_total += ot_cost

        # Add reconciliation rows
        paychex_emp = paychex_match_results.get(emp_name)
        paychex_wages = paychex_emp.gross_wages if paychex_emp else 0.0

        # Row 1: Calculated vs Paychex summary
        # Use 3 decimal precision for reconciliation amounts to show actual discrepancies
        output_rows.append({
            'Employee Name': emp_name,
            'Project/Job Code': None,
            'Hours': None,
            'Rate': 'Calculated:',
            'Amount': round(emp_calculated_total, 3),
            'Rate Type': 'Paychex:',
            'Notes': round(paychex_wages, 3) if paychex_emp else 'N/A'
        })

        # Row 2: Difference and status
        if paychex_emp:
            difference = round(emp_calculated_total - paychex_wages, 3)
            abs_diff = abs(difference)
            if abs_diff == 0:
                status = '✓ Reconciled'
            elif abs_diff <= 0.05:
                status = '⚡ Adjusted'
            else:
                status = '⚠️ CHECK'
        else:
            difference = emp_calculated_total
            status = '⚠️ NO PAYCHEX'

        output_rows.append({
            'Employee Name': None,
            'Project/Job Code': None,
            'Hours': None,
            'Rate': 'Difference:',
            'Amount': round(difference, 3),
            'Rate Type': None,
            'Notes': status
        })

        # Add blank row between employees
        output_rows.append({
            'Employee Name': None,
            'Project/Job Code': None,
            'Hours': None,
            'Rate': None,
            'Amount': None,
            'Rate Type': None,
            'Notes': None
        })

    # Convert to DataFrame
    output_df = pd.DataFrame(output_rows)

    # Write to Excel
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        output_df.to_excel(writer, sheet_name='Job Cost Allocation', index=False)

        # Format the sheet
        workbook = writer.book
        worksheet = writer.sheets['Job Cost Allocation']

        # Set column widths
        worksheet.column_dimensions['A'].width = 25   # Employee Name
        worksheet.column_dimensions['B'].width = 70   # Project/Job Code
        worksheet.column_dimensions['C'].width = 10   # Hours
        worksheet.column_dimensions['D'].width = 12   # Rate
        worksheet.column_dimensions['E'].width = 12   # Amount
        worksheet.column_dimensions['F'].width = 12   # Rate Type
        worksheet.column_dimensions['G'].width = 35   # Notes

        # Apply currency formatting to display values with $ and 2 decimal places
        # This is display-only - does not change the underlying calculated values
        for row in range(2, worksheet.max_row + 1):
            # Format Amount column (E) - all numeric values as currency with $
            amount_cell = worksheet.cell(row=row, column=5)
            if amount_cell.value is not None and isinstance(amount_cell.value, (int, float)):
                amount_cell.number_format = '"$"#,##0.00'

            # Format Paychex values in Notes column (G) - only numeric values with $
            notes_cell = worksheet.cell(row=row, column=7)
            if notes_cell.value is not None and isinstance(notes_cell.value, (int, float)):
                notes_cell.number_format = '"$"#,##0.00'

    # Build summary for return
    summary = {
        'output_file': output_file,
        'total_employees': len(sorted_employees),
        'total_rows': len(output_rows),
    }

    if reconciliation_report:
        summary['reconciliation'] = get_reconciliation_summary(reconciliation_report)

    return summary


def detect_overtime_and_prepare_selection(week1_file, week2_file):
    """
    Phase 1: Detect overtime situations and return data for user selection

    Returns:
    - ot_data: Dictionary with OT situations requiring user input
    - temp_data: Processed data to use in phase 2
    """
    # This follows the same initial processing as process_paychex_files
    # but stops before OT allocation to get user input

    # Read both files (same as main function)
    try:
        if week1_file.endswith('.csv') or week1_file.endswith('.txt'):
            df_week1 = pd.read_csv(week1_file, sep='\t', skiprows=4)
        else:
            df_week1 = pd.read_excel(week1_file, skiprows=4)

        if week2_file.endswith('.csv') or week2_file.endswith('.txt'):
            df_week2 = pd.read_csv(week2_file, sep='\t', skiprows=4)
        else:
            df_week2 = pd.read_excel(week2_file, skiprows=4)
    except Exception as e:
        return None, None

    df_week1['Week'] = 1
    df_week2['Week'] = 2
    df_combined = pd.concat([df_week1, df_week2], ignore_index=True)
    df_combined.columns = df_combined.columns.str.strip()

    # Parse duration
    df_combined['Hours_Decimal'] = df_combined['Duration'].apply(parse_duration_to_hours)

    # Extract employee names
    df_combined['Employee_Name'] = None
    current_employee = None
    for idx, row in df_combined.iterrows():
        first_col_value = row.iloc[0]
        activity_date = row['Activity date']

        # Skip grand total rows (Activity date contains 'TOTAL' string)
        if pd.notna(activity_date) and 'TOTAL' in str(activity_date).upper():
            continue

        if pd.isna(activity_date) and not pd.isna(first_col_value):
            if 'Total for' not in str(first_col_value):
                current_employee = str(first_col_value).strip()
        else:
            df_combined.at[idx, 'Employee_Name'] = current_employee

    df_work = df_combined[df_combined['Employee_Name'].notna()].copy()

    if len(df_work) == 0:
        return None, None

    # Debug: Show sample of parsed data
    print("\n[DEBUG] Sample of df_work (first 10 rows):")
    print(df_work[['Employee_Name', 'Week', 'Activity date', 'Customer full name', 'Hours_Decimal']].head(10).to_string())
    print(f"\n[DEBUG] Total rows in df_work: {len(df_work)}")

    # Calculate weekly hours
    weekly_hours = df_work.groupby(['Employee_Name', 'Week'])['Hours_Decimal'].sum().reset_index()
    weekly_hours.columns = ['Employee_Name', 'Week', 'Total_Week_Hours']

    # Debug: Print weekly hours to verify calculations
    print("\n[DEBUG] Weekly Hours Summary:")
    print(weekly_hours.to_string())
    print("\n[DEBUG] Employees with >40 hours:")
    print(weekly_hours[weekly_hours['Total_Week_Hours'] > 40].to_string())

    # Find OT situations (before merging to avoid duplicates)
    # Only include hourly employees - skip salaried employees
    ot_situations = []
    for _, row in weekly_hours[weekly_hours['Total_Week_Hours'] > 40].iterrows():
        emp_name = row['Employee_Name']
        
        # Skip salaried employees - they don't need OT allocation
        if is_employee_salaried(emp_name):
            print(f"\n[DEBUG] Skipping OT allocation for salaried employee: {emp_name}")
            continue
        
        week = row['Week']
        total_week_hours = row['Total_Week_Hours']
        total_ot = total_week_hours - 40

        print(f"\n[DEBUG] Processing OT for hourly employee {emp_name}, Week {week}: {total_week_hours} total hrs, {total_ot} OT hrs")

        # Get jobs worked during this week
        group = df_work[(df_work['Employee_Name'] == emp_name) & (df_work['Week'] == week)]

        jobs = []
        for idx, job_row in group.iterrows():
            # Create a stable job key for matching between phases
            job_key = create_job_key(
                emp_name,
                week,
                job_row['Activity date'],
                job_row['Customer full name'],
                job_row['Hours_Decimal']
            )
            jobs.append({
                'job_id': f"{emp_name}_{week}_{idx}",
                'date': str(job_row['Activity date']),
                'customer': str(job_row['Customer full name']),
                'hours': float(job_row['Hours_Decimal']),
                'job_key': job_key  # Use stable job_key instead of volatile index
            })

        ot_situations.append({
            'employee': emp_name,
            'week': int(week),
            'total_ot_hours': float(total_ot),
            'total_week_hours': float(total_week_hours),
            'jobs': jobs
        })

    return {
        'has_overtime': len(ot_situations) > 0,
        'ot_situations': ot_situations
    }, df_work

def process_paychex_files(week1_file, week2_file, output_file='job_costing_output.xlsx',
                         ot_allocations=None, paychex_payroll_file=None):
    """
    Process two QuickBooks weekly files and create job costing summary with optional Paychex validation.

    Parameters:
    - week1_file: Path to week 1 QuickBooks CSV/Excel file
    - week2_file: Path to week 2 QuickBooks CSV/Excel file
    - output_file: Path for output Excel file
    - ot_allocations: Optional dict of OT hour allocations from user
    - paychex_payroll_file: Optional path to Paychex payroll .xls file for validation
    """
    
    print("=" * 70)
    print("JOB COSTING CONVERSION TOOL - Rhea Engineering")
    print("=" * 70)
    print()
    
    # Read both files
    print(f"📂 Reading Week 1 file: {week1_file}")
    try:
        if week1_file.endswith('.csv') or week1_file.endswith('.txt'):
            df_week1 = pd.read_csv(week1_file, sep='\t', skiprows=4)
        else:
            # Skip first 4 rows (title, company name, date range, blank) and use row 4 as header
            df_week1 = pd.read_excel(week1_file, skiprows=4)
    except Exception as e:
        print(f"❌ Error reading Week 1 file: {e}")
        return None, None, None

    print(f"📂 Reading Week 2 file: {week2_file}")
    try:
        if week2_file.endswith('.csv') or week2_file.endswith('.txt'):
            df_week2 = pd.read_csv(week2_file, sep='\t', skiprows=4)
        else:
            # Skip first 4 rows (title, company name, date range, blank) and use row 4 as header
            df_week2 = pd.read_excel(week2_file, skiprows=4)
    except Exception as e:
        print(f"❌ Error reading Week 2 file: {e}")
        return None, None, None

    # Add week identifier to each dataframe
    df_week1['Week'] = 1
    df_week2['Week'] = 2
    
    # Combine both weeks
    df_combined = pd.concat([df_week1, df_week2], ignore_index=True)
    
    print(f"✓ Total records loaded: {len(df_combined)}")
    print()
    
    # Clean up column names (remove extra spaces)
    df_combined.columns = df_combined.columns.str.strip()

    # Validate required columns
    required_columns = ['Duration', 'Activity date', 'Customer full name', 'Rates']
    missing_columns = [col for col in required_columns if col not in df_combined.columns]

    if missing_columns:
        print(f"❌ Error: Missing required columns: {missing_columns}")
        print(f"   Columns found in file: {df_combined.columns.tolist()}")
        print()
        print("   Expected Paychex export format with columns:")
        print("   - Activity date")
        print("   - Customer full name")
        print("   - Duration (HH:MM format)")
        print("   - Rates")
        return None, None, None

    # Parse duration to decimal hours
    df_combined['Hours_Decimal'] = df_combined['Duration'].apply(parse_duration_to_hours)
    
    # Extract employee name from the first non-empty row after totals
    # This is a bit complex due to the data structure, so we'll handle it carefully
    
    # Create a new column to identify employee names
    # Employee names appear to be in rows where most other columns are empty
    df_combined['Employee_Name'] = None

    current_employee = None
    for idx, row in df_combined.iterrows():
        # Check if this is an employee name row (Activity date is empty but there's text in first column)
        # Employee name is in the first column (Unnamed: 0)
        first_col_value = row.iloc[0]
        activity_date = row['Activity date']

        # Skip grand total rows (Activity date contains 'TOTAL' string)
        if pd.notna(activity_date) and 'TOTAL' in str(activity_date).upper():
            continue

        if pd.isna(activity_date) and not pd.isna(first_col_value):
            # Check if it's not a "Total for" row
            if 'Total for' not in str(first_col_value):
                current_employee = str(first_col_value).strip()
        else:
            df_combined.at[idx, 'Employee_Name'] = current_employee

    # Remove rows without employee names (header rows, total rows, etc.)
    df_work = df_combined[df_combined['Employee_Name'].notna()].copy()
    
    print(f"✓ Cleaned data: {len(df_work)} work records found")
    print(f"✓ Employees found: {df_work['Employee_Name'].nunique()}")
    print()

    # Check if we have any work records
    if len(df_work) == 0:
        print("❌ Error: No work records found after cleaning")
        print("   This could mean:")
        print("   - Employee names are not being detected correctly")
        print("   - File format is different than expected")
        return None, None, None

    # Validate all employees exist in the master file
    paychex_employees = df_work['Employee_Name'].unique().tolist()
    validation = validate_employees_against_paychex(paychex_employees)

    if not validation['valid']:
        print(f"⚠️  Found {len(validation['unknown'])} employees not in master roster:")
        for emp in validation['unknown']:
            print(f"   - {emp}")
        print()
        print("   Please add these employees to the roster before processing.")
        # Return the unknown employees so the UI can prompt the user
        # Return 4 values to match normal return signature
        return None, None, validation['unknown'], None

    # Calculate weekly hours by employee to determine overtime
    weekly_hours = df_work.groupby(['Employee_Name', 'Week'])['Hours_Decimal'].sum().reset_index()
    weekly_hours.columns = ['Employee_Name', 'Week', 'Total_Week_Hours']
    
    # Merge back to main dataframe
    df_work = df_work.merge(weekly_hours, on=['Employee_Name', 'Week'], how='left')
    
    # Determine if employee has overtime this week (>40 hours)
    df_work['Has_OT_This_Week'] = df_work['Total_Week_Hours'] > 40

    # Initialize OT columns
    df_work['Regular_Hours'] = df_work['Hours_Decimal']
    df_work['OT_Hours'] = 0.0

    # Apply user-selected OT allocations if provided
    if ot_allocations:
        # ot_allocations format: {employee_week: {job_key: ot_hours}}
        # Example: {'Amy C. Brown_1': {'Amy C. Brown|1|2024-09-15|Project A|8.0': 3.5}}

        # Create job keys for all rows to enable matching
        df_work['job_key'] = df_work.apply(
            lambda row: create_job_key(
                row['Employee_Name'],
                row['Week'],
                row['Activity date'],
                row['Customer full name'],
                row['Hours_Decimal']
            ),
            axis=1
        )

        allocation_count = 0
        for key, allocations in ot_allocations.items():
            for job_key, ot_hours in allocations.items():
                # Find rows matching this job_key
                matching_rows = df_work[df_work['job_key'] == job_key]

                if len(matching_rows) > 0:
                    idx = matching_rows.index[0]
                    # Assign the OT hours to this specific job
                    df_work.at[idx, 'OT_Hours'] = float(ot_hours)
                    # Subtract OT from total to get regular hours
                    df_work.at[idx, 'Regular_Hours'] = df_work.at[idx, 'Hours_Decimal'] - float(ot_hours)
                    allocation_count += 1
                    print(f"[DEBUG] Allocated {ot_hours} OT hours to: {job_key[:60]}...")
                else:
                    print(f"[WARNING] Could not find job with key: {job_key}")

        print(f"\n[DEBUG] Total OT allocations applied: {allocation_count}")

        # Clean up the temporary job_key column
        df_work = df_work.drop(columns=['job_key'])
    else:
        # Fallback: Use proportional allocation if no user selection provided
        # Note: This path is used when no hourly employees have OT, but we still
        # need to ensure salaried employees never get OT hours calculated
        def calculate_regular_and_ot_hours(row):
            """Calculate regular and OT hours for each row"""
            # IMPORTANT: Salaried employees NEVER get OT multiplier
            # They get rate adjustment instead (handled in get_employee_rate)
            if is_employee_salaried(row['Employee_Name']):
                return row['Hours_Decimal'], 0.0

            if not row['Has_OT_This_Week']:
                return row['Hours_Decimal'], 0.0
            else:
                total_week_hours = row['Total_Week_Hours']
                regular_cap = 40.0
                ot_hours_total = total_week_hours - regular_cap
                proportion = row['Hours_Decimal'] / total_week_hours
                ot_hours_this_entry = ot_hours_total * proportion
                regular_hours_this_entry = row['Hours_Decimal'] - ot_hours_this_entry
                return regular_hours_this_entry, ot_hours_this_entry

        result = df_work.apply(calculate_regular_and_ot_hours, axis=1, result_type='expand')
        df_work['Regular_Hours'] = result[0]
        df_work['OT_Hours'] = result[1]

    # CRITICAL FIX: Enforce the invariant that Regular_Hours + OT_Hours == Hours_Decimal
    # OT hours are a SUBSET of total hours worked, not additional hours.
    # When OT is allocated to a job, it splits Hours_Decimal into:
    #   - Regular_Hours: paid at normal rate
    #   - OT_Hours: paid at 1.5x rate (for hourly employees)
    # The Excel output creates separate rows for each, so they must sum to actual hours.
    df_work['Regular_Hours'] = df_work['Hours_Decimal'] - df_work['OT_Hours']

    # Validation logging: Show OT allocation summary and verify invariant
    ot_summary = df_work.groupby('Employee_Name').agg({
        'OT_Hours': 'sum',
        'Regular_Hours': 'sum',
        'Hours_Decimal': 'sum'
    }).reset_index()

    # Verify invariant: Regular_Hours + OT_Hours == Hours_Decimal for all employees
    total_hours_decimal = ot_summary['Hours_Decimal'].sum()
    total_regular = ot_summary['Regular_Hours'].sum()
    total_ot = ot_summary['OT_Hours'].sum()

    print(f"\n[DEBUG] Hours Verification (Regular + OT should equal Total):")
    print(f"  Total Hours (from source): {total_hours_decimal:.2f}")
    print(f"  Regular Hours: {total_regular:.2f}")
    print(f"  OT Hours: {total_ot:.2f}")
    print(f"  Sum (Regular + OT): {total_regular + total_ot:.2f}")

    if abs(total_hours_decimal - (total_regular + total_ot)) > 0.01:
        print(f"  ⚠️  MISMATCH: Difference of {total_hours_decimal - (total_regular + total_ot):.2f} hours!")
    else:
        print(f"  ✓ Verified: Hours balance correctly")

    employees_with_ot = ot_summary[ot_summary['OT_Hours'] > 0]
    if len(employees_with_ot) > 0:
        print("\n[DEBUG] OT Allocation by Employee:")
        for _, row in employees_with_ot.iterrows():
            reg_plus_ot = row['Regular_Hours'] + row['OT_Hours']
            status = "✓" if abs(row['Hours_Decimal'] - reg_plus_ot) < 0.01 else "⚠️"
            print(f"  {status} {row['Employee_Name']}: {row['Regular_Hours']:.2f} reg + "
                  f"{row['OT_Hours']:.2f} OT = {reg_plus_ot:.2f} (actual: {row['Hours_Decimal']:.2f})")
    else:
        print("\n[DEBUG] No OT hours allocated to any employee")

    # Calculate total hours per employee for salaried rate adjustment
    employee_total_hours = df_work.groupby('Employee_Name')['Hours_Decimal'].sum().to_dict()

    # Get rate for each employee from master file with salaried adjustment
    def get_rate_for_employee(emp_name):
        """Look up employee rate from master file, applying salaried adjustment if needed"""
        total_hours = employee_total_hours.get(emp_name, 80.0)
        rate, base_rate, is_adjusted = get_employee_rate(emp_name, total_hours)
        if rate is not None:
            return rate
        # Fallback (should not happen since we validated earlier)
        print(f"⚠️  Warning: No rate found for {emp_name}, using 0")
        return 0.0

    # Apply rates from employee master file
    df_work['Hourly_Rate'] = df_work['Employee_Name'].apply(get_rate_for_employee)

    # Calculate costs
    df_work['Regular_Cost'] = df_work['Regular_Hours'] * df_work['Hourly_Rate']
    df_work['OT_Cost'] = df_work['OT_Hours'] * df_work['Hourly_Rate'] * 1.5  # Time and a half
    df_work['Total_Cost'] = df_work['Regular_Cost'] + df_work['OT_Cost']
    
    # Group by Employee and Customer
    summary = df_work.groupby(['Employee_Name', 'Customer full name']).agg({
        'Regular_Hours': 'sum',
        'OT_Hours': 'sum',
        'Hourly_Rate': 'first',
        'Regular_Cost': 'sum',
        'OT_Cost': 'sum',
        'Total_Cost': 'sum'
    }).reset_index()
    
    # Sort by Employee Name, then Customer Name
    summary = summary.sort_values(['Employee_Name', 'Customer full name'])
    
    # Round to 2 decimal places
    summary['Regular_Hours'] = summary['Regular_Hours'].round(2)
    summary['OT_Hours'] = summary['OT_Hours'].round(2)
    summary['Regular_Cost'] = summary['Regular_Cost'].round(2)
    summary['OT_Cost'] = summary['OT_Cost'].round(2)
    summary['Total_Cost'] = summary['Total_Cost'].round(2)
    
    # Create employee totals with detailed rate information for transparency
    employee_totals_list = []
    for emp_name in df_work['Employee_Name'].unique():
        emp_data = df_work[df_work['Employee_Name'] == emp_name]
        total_hours = emp_data['Hours_Decimal'].sum()
        regular_hours = emp_data['Regular_Hours'].sum()
        ot_hours = emp_data['OT_Hours'].sum()
        total_cost = emp_data['Total_Cost'].sum()

        # Get rate info - pass 80 to get the base rate without adjustment
        _, base_rate, _ = get_employee_rate(emp_name, 80.0)
        # Get the actual rate used (which may be adjusted for salaried)
        actual_rate = emp_data['Hourly_Rate'].iloc[0]

        is_salaried = is_employee_salaried(emp_name)

        # Calculate Payrolled Hours: what should match Paychex
        # - Salaried employees: capped at 80 (they don't get paid for hours over 80)
        # - Hourly employees: all hours (regular + OT, since OT is paid at 1.5x)
        if is_salaried:
            payrolled_hours = min(total_hours, 80.0)
        else:
            payrolled_hours = total_hours  # Hourly employees get paid for all hours

        employee_totals_list.append({
            'Employee_Name': emp_name,
            'Total_Hours': round(total_hours, 2),
            'Payrolled_Hours': round(payrolled_hours, 2),
            'Regular_Hours': round(regular_hours, 2),
            'OT_Hours': round(ot_hours, 2),
            'Base_Rate': round(base_rate, 2) if base_rate else 0,
            # Only show Adjusted Rate for salaried employees who worked >80 hours
            'Adjusted_Rate': round(actual_rate, 2) if is_salaried and total_hours > 80 else "-",
            # Only show OT Rate for hourly employees with overtime
            'OT_Rate': round(base_rate * 1.5, 2) if not is_salaried and ot_hours > 0 else "-",
            'Total_Cost': round(total_cost, 2)
        })

    employee_totals = pd.DataFrame(employee_totals_list)

    print("📊 Summary Statistics:")
    print("-" * 70)
    for _, emp in employee_totals.iterrows():
        print(f"\n{emp['Employee_Name']}:")
        hours_note = ""
        if emp['Total_Hours'] != emp['Payrolled_Hours']:
            hours_note = f" → Payrolled: {emp['Payrolled_Hours']:.2f}"
        print(f"  Actual Hours: {emp['Total_Hours']:.2f} (Reg: {emp['Regular_Hours']:.2f}, OT: {emp['OT_Hours']:.2f}){hours_note}")
        print(f"  Base Rate: ${emp['Base_Rate']:.2f}")
        if emp['Adjusted_Rate'] != "-":
            print(f"  Adjusted Rate: ${emp['Adjusted_Rate']:.2f} (salaried)")
        if emp['OT_Rate'] != "-":
            print(f"  OT Rate: ${emp['OT_Rate']:.2f}")
        print(f"  Total Cost: ${emp['Total_Cost']:,.2f}")

    # Grand totals for reconciliation
    grand_actual_hours = employee_totals['Total_Hours'].sum()
    grand_payrolled_hours = employee_totals['Payrolled_Hours'].sum()
    grand_cost = employee_totals['Total_Cost'].sum()

    print("\n" + "=" * 70)
    print("📋 GRAND TOTALS (for Paychex reconciliation)")
    print("=" * 70)
    print(f"  Actual Hours Worked:  {grand_actual_hours:,.2f}")
    print(f"  Payrolled Hours:      {grand_payrolled_hours:,.2f}  ← Should match Paychex")
    if grand_actual_hours != grand_payrolled_hours:
        diff = grand_actual_hours - grand_payrolled_hours
        print(f"  Difference:           {diff:,.2f} (salaried employees worked {diff:.2f} unpaid OT hours)")
    print(f"  Total Cost:           ${grand_cost:,.2f}")
    print()
    
    # Handle Paychex validation if file provided
    paychex_match_results = {}
    reconciliation_report = None
    reconciliation_summary = None

    if paychex_payroll_file:
        print(f"\n📋 Processing Paychex validation file: {paychex_payroll_file}")
        try:
            # Parse Paychex file
            paychex_data = parse_paychex_file(paychex_payroll_file)
            print(f"   Found {len(paychex_data)} employees in Paychex file")

            # Get name aliases for matching
            name_aliases = get_paychex_name_aliases()

            # Match QB employees to Paychex
            qb_employees = list(df_work['Employee_Name'].unique())
            match_result = match_employees(qb_employees, paychex_data, name_aliases)

            paychex_match_results = match_result.matched
            print(f"   Matched: {len(match_result.matched)} employees")
            if match_result.unmatched_qb:
                print(f"   ⚠️  Unmatched in QB: {match_result.unmatched_qb}")
            if match_result.unmatched_paychex:
                print(f"   ⚠️  Unmatched in Paychex: {match_result.unmatched_paychex}")

            # Build employee totals for reconciliation
            employee_totals_for_recon = {}
            for emp_name in qb_employees:
                emp_data = df_work[df_work['Employee_Name'] == emp_name]
                total_hours = emp_data['Hours_Decimal'].sum()
                rate, base_rate, is_adjusted = get_employee_rate(emp_name, total_hours)

                employee_totals_for_recon[emp_name] = {
                    'total_cost': emp_data['Total_Cost'].sum(),
                    'regular_hours': emp_data['Regular_Hours'].sum(),
                    'ot_hours': emp_data['OT_Hours'].sum(),
                    'base_rate': base_rate,
                    'adjusted_rate': rate if is_adjusted else None
                }

            # Generate reconciliation report
            reconciliation_report = generate_reconciliation_report(
                employee_totals_for_recon,
                paychex_match_results,
                match_result.unmatched_qb,
                match_result.unmatched_paychex
            )

            reconciliation_summary = get_reconciliation_summary(reconciliation_report)

            print(f"\n📊 Reconciliation Summary:")
            print(f"   ✓ Reconciled: {reconciliation_report.total_reconciled}")
            print(f"   ⚡ Adjusted:   {reconciliation_report.total_adjusted}")
            print(f"   ⚠️  Need Review: {reconciliation_report.total_check}")

        except Exception as e:
            print(f"   ❌ Error processing Paychex file: {e}")
            import traceback
            traceback.print_exc()

    # Generate output file - ALWAYS use unified Job Cost Allocation format
    print(f"\n💾 Writing output to: {output_file}")

    # Always use single-sheet Job Cost Allocation format (unified output)
    # When Paychex is provided: full reconciliation with ✓/⚡/⚠️ status
    # When Paychex is missing: reconciliation shows "N/A" and "⚠️ NO PAYCHEX"
    output_summary = generate_job_cost_allocation_output(
        df_work=df_work,
        paychex_match_results=paychex_match_results,  # May be empty dict if no Paychex
        reconciliation_report=reconciliation_report,   # May be None if no Paychex
        output_file=output_file
    )

    print("✅ Job costing conversion complete!")
    print()
    print(f"📈 Output file created: {output_file}")
    if paychex_payroll_file and paychex_match_results:
        print(f"   - Sheet: Job Cost Allocation (with Paychex reconciliation)")
    else:
        print(f"   - Sheet: Job Cost Allocation (no Paychex - reconciliation shows N/A)")
    print()
    print("=" * 70)

    return summary, employee_totals, None, reconciliation_summary

if __name__ == "__main__":
    # Example usage
    if len(sys.argv) >= 3:
        week1_file = sys.argv[1]
        week2_file = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else 'job_costing_output.xlsx'
    else:
        # Default test files (update these paths)
        print("Usage: python job_costing_converter.py <week1_file> <week2_file> [output_file]")
        print()
        print("Using default test files from current directory...")
        week1_file = "paychex_week1.xlsx"
        week2_file = "paychex_week2.xlsx"
        output_file = "job_costing_output.xlsx"
    
    # Process the files
    summary, totals, unknown_employees, _ = process_paychex_files(week1_file, week2_file, output_file)

    if unknown_employees:
        print(f"\n⚠️  Cannot process: {len(unknown_employees)} unknown employees need to be added to roster first.")
        for emp in unknown_employees:
            print(f"   - {emp}")
