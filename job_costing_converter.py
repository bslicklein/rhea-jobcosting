import pandas as pd
import numpy as np
from datetime import datetime
import sys
import json
from employee_master import is_employee_salaried, get_employee_rate, validate_employees_against_paychex

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
        if pd.isna(row['Activity date']) and not pd.isna(first_col_value):
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
            jobs.append({
                'job_id': f"{emp_name}_{week}_{idx}",
                'date': str(job_row['Activity date']),
                'customer': str(job_row['Customer full name']),
                'hours': float(job_row['Hours_Decimal']),
                'index': int(idx)
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

def process_paychex_files(week1_file, week2_file, output_file='job_costing_output.xlsx', ot_allocations=None):
    """
    Process two Paychex weekly files and create job costing summary
    
    Parameters:
    - week1_file: Path to week 1 CSV/Excel file
    - week2_file: Path to week 2 CSV/Excel file
    - output_file: Path for output Excel file
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
        if pd.isna(row['Activity date']) and not pd.isna(first_col_value):
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
        return None, None, validation['unknown']

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
        # ot_allocations format: {employee_week: {job_index: ot_hours}}
        # Example: {'Amy C. Brown_1': {5: 0.3, 12: 0.2}}

        for key, allocations in ot_allocations.items():
            for job_index, ot_hours in allocations.items():
                if job_index in df_work.index:
                    # Assign the OT hours to this specific job
                    df_work.at[job_index, 'OT_Hours'] = ot_hours
                    # Subtract OT from total to get regular hours
                    df_work.at[job_index, 'Regular_Hours'] = df_work.at[job_index, 'Hours_Decimal'] - ot_hours
    else:
        # Fallback: Use proportional allocation if no user selection provided
        def calculate_regular_and_ot_hours(row):
            """Calculate regular and OT hours for each row"""
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
    
    # Create employee totals
    employee_totals = summary.groupby('Employee_Name').agg({
        'Regular_Hours': 'sum',
        'OT_Hours': 'sum',
        'Regular_Cost': 'sum',
        'OT_Cost': 'sum',
        'Total_Cost': 'sum'
    }).reset_index()
    
    print("📊 Summary Statistics:")
    print("-" * 70)
    for _, emp in employee_totals.iterrows():
        print(f"\n{emp['Employee_Name']}:")
        print(f"  Regular Hours: {emp['Regular_Hours']:.2f}")
        print(f"  OT Hours: {emp['OT_Hours']:.2f}")
        print(f"  Total Cost: ${emp['Total_Cost']:,.2f}")
    print()
    
    # Write to Excel with formatting
    print(f"💾 Writing output to: {output_file}")
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        # Write main summary
        summary.to_excel(writer, sheet_name='Job Costing Summary', index=False)
        
        # Write employee totals
        employee_totals.to_excel(writer, sheet_name='Employee Totals', index=False)
        
        # Write detailed data for audit trail
        df_work[['Employee_Name', 'Activity date', 'Customer full name', 'Description', 
                 'Week', 'Hours_Decimal', 'Regular_Hours', 'OT_Hours', 'Hourly_Rate',
                 'Total_Cost']].to_excel(writer, sheet_name='Detailed Records', index=False)
        
        # Format the main summary sheet
        workbook = writer.book
        worksheet = writer.sheets['Job Costing Summary']
        
        # Set column widths
        worksheet.column_dimensions['A'].width = 25  # Employee Name
        worksheet.column_dimensions['B'].width = 50  # Customer Name
        worksheet.column_dimensions['C'].width = 15  # Regular Hours
        worksheet.column_dimensions['D'].width = 15  # OT Hours
        worksheet.column_dimensions['E'].width = 15  # Hourly Rate
        worksheet.column_dimensions['F'].width = 15  # Regular Cost
        worksheet.column_dimensions['G'].width = 15  # OT Cost
        worksheet.column_dimensions['H'].width = 15  # Total Cost
    
    print("✅ Job costing conversion complete!")
    print()
    print(f"📈 Output file created: {output_file}")
    print(f"   - Sheet 1: Job Costing Summary (by employee & customer)")
    print(f"   - Sheet 2: Employee Totals")
    print(f"   - Sheet 3: Detailed Records (audit trail)")
    print()
    print("=" * 70)

    return summary, employee_totals, None

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
    summary, totals, unknown_employees = process_paychex_files(week1_file, week2_file, output_file)

    if unknown_employees:
        print(f"\n⚠️  Cannot process: {len(unknown_employees)} unknown employees need to be added to roster first.")
        for emp in unknown_employees:
            print(f"   - {emp}")
