"""
Paychex Payroll File Parser

Parses Paychex .xls payroll exports to extract employee names, gross wages,
and hours breakdown for reconciliation with job costing calculations.

Expected Paychex file format:
- Column: 'Employee Information' - Employee name in "Last, First M." format
- Column: 'Salary' - Gross wages (source of truth for reconciliation)
- Column: 'Reg Hrs' - Regular hours worked
- Column: 'O/T Hr' - Overtime hours
- Column: 'PTO' - PTO hours
- Column: 'Holiday' - Holiday hours
- Column: 'NEW RATES' - Base hourly rate
"""

import pandas as pd
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class PaychexEmployee:
    """Data structure for a single employee's Paychex payroll data."""
    raw_name: str           # Original name format from Paychex
    normalized_name: str    # Normalized for matching
    gross_wages: float      # From 'Salary' column - source of truth
    regular_hours: float    # From 'Reg Hrs'
    ot_hours: float         # From 'O/T Hr'
    pto_hours: float        # From 'PTO'
    holiday_hours: float    # From 'Holiday'
    other_hours: float      # From 'Other: Bereav Jury' or similar
    base_rate: float        # From 'NEW RATES'

    @property
    def total_hours(self) -> float:
        """Total hours from all hour types."""
        return self.regular_hours + self.ot_hours + self.pto_hours + self.holiday_hours + self.other_hours


@dataclass
class MatchResult:
    """Result of matching QuickBooks employees to Paychex records."""
    matched: Dict[str, PaychexEmployee]  # qb_name -> PaychexEmployee
    unmatched_qb: List[str]              # In QB but not in Paychex
    unmatched_paychex: List[str]         # In Paychex but not in QB


def normalize_name(name: str, source_format: str = 'auto') -> str:
    """
    Normalize employee name to canonical form for cross-system matching.

    Handles:
    - Paychex format: "Last, First M." -> "first m last"
    - QuickBooks format: "First M. Last" -> "first m last"
    - Extra whitespace, periods, case differences

    Args:
        name: The employee name to normalize
        source_format: 'paychex', 'quickbooks', or 'auto' (detect by comma presence)

    Returns:
        Normalized name in "first middle last" format, lowercase
    """
    if not name or not isinstance(name, str):
        return ""

    # Clean up the name
    name = name.strip()
    name = re.sub(r'\s+', ' ', name)  # Collapse multiple spaces
    name = re.sub(r'\.', '', name)     # Remove periods
    name = name.lower()

    # Auto-detect format if needed
    if source_format == 'auto':
        source_format = 'paychex' if ',' in name else 'quickbooks'

    if source_format == 'paychex' and ',' in name:
        # "last, first m" -> "first m last"
        parts = name.split(',', 1)
        last = parts[0].strip()
        first_middle = parts[1].strip() if len(parts) > 1 else ''
        return f"{first_middle} {last}".strip()
    else:
        # Already in "first m last" format
        return name.strip()


def safe_float(value, default: float = 0.0) -> float:
    """Safely convert a value to float, returning default if conversion fails."""
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def parse_paychex_file(filepath: str) -> Dict[str, PaychexEmployee]:
    """
    Parse a Paychex payroll export file (.xls or .xlsx format).

    The Paychex file has a specific structure where employee data appears
    in rows that have a non-zero Salary value. Each employee's data spans
    multiple rows (name row, title row, etc.), but we only need the row
    with the salary.

    Args:
        filepath: Path to the Paychex .xls or .xlsx file

    Returns:
        Dictionary mapping normalized employee name -> PaychexEmployee
    """
    # Determine engine based on file extension
    if filepath.lower().endswith('.xls'):
        df = pd.read_excel(filepath, engine='xlrd')
    else:
        df = pd.read_excel(filepath, engine='openpyxl')

    employees = {}

    # Expected column names (may vary slightly)
    emp_info_col = 'Employee Information'
    salary_col = 'Salary'
    reg_hrs_col = 'Reg Hrs'
    ot_hrs_col = 'O/T Hr'
    pto_col = 'PTO'
    holiday_col = 'Holiday'
    other_col = 'Other: Bereav  Jury'  # Note: may have extra spaces
    rate_col = 'NEW RATES'

    # Find the actual column names (handle variations)
    actual_cols = df.columns.tolist()

    # Find columns that contain our expected patterns
    def find_column(patterns: List[str]) -> Optional[str]:
        for col in actual_cols:
            col_lower = str(col).lower().replace(' ', '')
            for pattern in patterns:
                if pattern.lower().replace(' ', '') in col_lower:
                    return col
        return None

    emp_info_col = find_column(['employeeinformation', 'employee']) or emp_info_col
    salary_col = find_column(['salary']) or salary_col
    reg_hrs_col = find_column(['reghrs', 'regularhours']) or reg_hrs_col
    ot_hrs_col = find_column(['o/thr', 'othrs', 'overtimehours']) or ot_hrs_col
    pto_col = find_column(['pto']) or pto_col
    holiday_col = find_column(['holiday']) or holiday_col
    other_col = find_column(['other', 'bereav', 'jury']) or other_col
    rate_col = find_column(['newrates', 'rate']) or rate_col

    # Skip the "Total All Columns" row and other summary rows
    skip_patterns = ['total', 'all columns', 'subtotal']

    for idx, row in df.iterrows():
        emp_info = row.get(emp_info_col)
        salary = row.get(salary_col)

        # Skip if no employee info or no salary (or salary is 0)
        if pd.isna(emp_info) or not isinstance(emp_info, str):
            continue

        # Skip summary rows
        emp_lower = emp_info.lower()
        if any(pattern in emp_lower for pattern in skip_patterns):
            continue

        # Skip if salary is missing or zero
        salary_val = safe_float(salary, 0.0)
        if salary_val == 0:
            continue

        # Extract all the data
        raw_name = emp_info.strip()
        normalized = normalize_name(raw_name, 'paychex')

        employee = PaychexEmployee(
            raw_name=raw_name,
            normalized_name=normalized,
            gross_wages=salary_val,
            regular_hours=safe_float(row.get(reg_hrs_col)),
            ot_hours=safe_float(row.get(ot_hrs_col)),
            pto_hours=safe_float(row.get(pto_col)),
            holiday_hours=safe_float(row.get(holiday_col)),
            other_hours=safe_float(row.get(other_col)),
            base_rate=safe_float(row.get(rate_col))
        )

        # Use normalized name as key for matching
        employees[normalized] = employee

    return employees


def match_employees(
    qb_employees: List[str],
    paychex_data: Dict[str, PaychexEmployee],
    name_aliases: Optional[Dict[str, str]] = None
) -> MatchResult:
    """
    Match QuickBooks employee names to Paychex records.

    Uses a multi-step matching strategy:
    1. Exact normalized name match
    2. Fuzzy matching (first + last name only)
    3. Alias lookup from employee master

    Args:
        qb_employees: List of employee names from QuickBooks
        paychex_data: Dictionary from parse_paychex_file()
        name_aliases: Optional dict mapping QB name -> Paychex name

    Returns:
        MatchResult with matched employees and unmatched lists
    """
    name_aliases = name_aliases or {}

    matched = {}
    unmatched_qb = []
    used_paychex = set()

    for qb_name in qb_employees:
        qb_normalized = normalize_name(qb_name, 'quickbooks')
        found = False

        # Strategy 1: Exact normalized match
        if qb_normalized in paychex_data:
            matched[qb_name] = paychex_data[qb_normalized]
            used_paychex.add(qb_normalized)
            found = True
            continue

        # Strategy 2: Check aliases
        if qb_name in name_aliases:
            alias_normalized = normalize_name(name_aliases[qb_name], 'paychex')
            if alias_normalized in paychex_data:
                matched[qb_name] = paychex_data[alias_normalized]
                used_paychex.add(alias_normalized)
                found = True
                continue

        # Strategy 3: Fuzzy match - try first+last only (drop middle)
        qb_parts = qb_normalized.split()
        if len(qb_parts) >= 2:
            first_last = f"{qb_parts[0]} {qb_parts[-1]}"
            for paychex_normalized, paychex_emp in paychex_data.items():
                if paychex_normalized in used_paychex:
                    continue
                paychex_parts = paychex_normalized.split()
                if len(paychex_parts) >= 2:
                    paychex_first_last = f"{paychex_parts[0]} {paychex_parts[-1]}"
                    if first_last == paychex_first_last:
                        matched[qb_name] = paychex_emp
                        used_paychex.add(paychex_normalized)
                        found = True
                        break

        if not found:
            unmatched_qb.append(qb_name)

    # Find unmatched Paychex employees
    unmatched_paychex = [
        emp.raw_name for norm_name, emp in paychex_data.items()
        if norm_name not in used_paychex
    ]

    return MatchResult(
        matched=matched,
        unmatched_qb=unmatched_qb,
        unmatched_paychex=unmatched_paychex
    )


def get_paychex_summary(paychex_data: Dict[str, PaychexEmployee]) -> dict:
    """
    Generate a summary of the Paychex data for display/debugging.

    Returns:
        Dictionary with summary statistics
    """
    if not paychex_data:
        return {
            'total_employees': 0,
            'total_gross_wages': 0.0,
            'total_regular_hours': 0.0,
            'total_ot_hours': 0.0,
            'employees': []
        }

    total_wages = sum(emp.gross_wages for emp in paychex_data.values())
    total_reg = sum(emp.regular_hours for emp in paychex_data.values())
    total_ot = sum(emp.ot_hours for emp in paychex_data.values())

    employee_list = [
        {
            'name': emp.raw_name,
            'normalized': emp.normalized_name,
            'gross_wages': emp.gross_wages,
            'regular_hours': emp.regular_hours,
            'ot_hours': emp.ot_hours,
            'total_hours': emp.total_hours
        }
        for emp in paychex_data.values()
    ]

    return {
        'total_employees': len(paychex_data),
        'total_gross_wages': total_wages,
        'total_regular_hours': total_reg,
        'total_ot_hours': total_ot,
        'employees': employee_list
    }
