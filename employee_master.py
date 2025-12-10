"""
Employee Master Data Management for Rhea Job Costing Tool

This module handles:
- Loading/saving employee data (salaried vs hourly, rates)
- Calculating adjusted rates for salaried employees
- Validating employees against Paychex data
"""

import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# Default employee data file location
DEFAULT_EMPLOYEES_FILE = os.path.join(os.path.dirname(__file__), 'employees.json')


@dataclass
class Employee:
    """Employee data structure"""
    name: str                    # Name as it appears in QuickBooks
    employee_type: str           # 'salaried' or 'hourly'
    base_rate: float             # Base hourly rate
    qb_indirect_code: str = ""   # QuickBooks indirect labor code
    qb_direct_code: str = ""     # QuickBooks direct labor code
    paychex_name: str = ""       # Name as it appears in Paychex (if different from QB)
    is_owner: bool = False       # True for owners taking distributions (excluded from job costing)

    def is_salaried(self) -> bool:
        return self.employee_type.lower() == 'salaried'

    def is_hourly(self) -> bool:
        return self.employee_type.lower() == 'hourly'

    def get_paychex_name(self) -> str:
        """Get the Paychex name (uses QB name if no alias set)."""
        return self.paychex_name if self.paychex_name else self.name

    def should_job_cost(self) -> bool:
        """Check if this employee should be included in job costing calculations.

        Owners taking distributions are excluded because they have no labor cost -
        their compensation comes from profits, not wages.
        """
        return not self.is_owner


def load_employees(filepath: str = DEFAULT_EMPLOYEES_FILE) -> Dict[str, Employee]:
    """
    Load employee data from JSON file

    Returns: Dictionary mapping employee name -> Employee object
    """
    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        employees = {}
        for emp_data in data.get('employees', []):
            emp = Employee(
                name=emp_data['name'],
                employee_type=emp_data['employee_type'],
                base_rate=float(emp_data['base_rate']),
                qb_indirect_code=emp_data.get('qb_indirect_code', ''),
                qb_direct_code=emp_data.get('qb_direct_code', ''),
                paychex_name=emp_data.get('paychex_name', ''),
                is_owner=emp_data.get('is_owner', False)
            )
            employees[emp.name] = emp

        return employees
    except Exception as e:
        print(f"Error loading employees: {e}")
        return {}


def save_employees(employees: Dict[str, Employee], filepath: str = DEFAULT_EMPLOYEES_FILE) -> bool:
    """
    Save employee data to JSON file

    Returns: True if successful, False otherwise
    """
    try:
        data = {
            'last_updated': datetime.now().isoformat(),
            'employees': [asdict(emp) for emp in employees.values()]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        return True
    except Exception as e:
        print(f"Error saving employees: {e}")
        return False


def get_employee_list() -> List[Dict]:
    """
    Get all employees as a list of dictionaries (for API/UI)
    """
    employees = load_employees()
    return [
        {
            'name': emp.name,
            'employee_type': emp.employee_type,
            'base_rate': emp.base_rate,
            'qb_indirect_code': emp.qb_indirect_code,
            'qb_direct_code': emp.qb_direct_code,
            'paychex_name': emp.paychex_name,
            'is_salaried': emp.is_salaried(),
            'is_owner': emp.is_owner
        }
        for emp in employees.values()
    ]


def get_paychex_name_aliases() -> Dict[str, str]:
    """
    Get mapping of QB names to Paychex names for employees with aliases.

    Returns: Dict mapping QB name -> Paychex name (only for employees with aliases)
    """
    employees = load_employees()
    return {
        emp.name: emp.paychex_name
        for emp in employees.values()
        if emp.paychex_name and emp.paychex_name != emp.name
    }


def update_employee(name: str, employee_type: str, base_rate: float,
                   qb_indirect_code: str = "", qb_direct_code: str = "",
                   paychex_name: str = "", is_owner: bool = False) -> bool:
    """
    Add or update a single employee
    """
    employees = load_employees()
    employees[name] = Employee(
        name=name,
        employee_type=employee_type,
        base_rate=base_rate,
        qb_indirect_code=qb_indirect_code,
        qb_direct_code=qb_direct_code,
        paychex_name=paychex_name,
        is_owner=is_owner
    )
    return save_employees(employees)


def delete_employee(name: str) -> bool:
    """
    Delete an employee by name
    """
    employees = load_employees()
    if name in employees:
        del employees[name]
        return save_employees(employees)
    return False


def calculate_adjusted_rate(base_rate: float, total_hours: float, standard_hours: float = 80.0) -> float:
    """
    Calculate the adjusted hourly rate for salaried employees

    Formula: (Base Rate × Standard Hours) ÷ Actual Hours = Adjusted Rate

    Example:
    - Base rate: $67.36/hour
    - Standard hours: 80 (per pay period)
    - Actual hours worked: 95
    - Adjusted rate: ($67.36 × 80) ÷ 95 = $56.72/hour

    This ensures that salaried employees' total pay stays the same regardless
    of hours worked, which is required for federal audit compliance.
    """
    if total_hours <= 0:
        return base_rate

    # If they worked less than or equal to standard hours, use base rate
    # (we don't inflate the rate if they worked fewer hours)
    if total_hours <= standard_hours:
        return base_rate

    # Adjusted rate = (base_rate × 80) / actual_hours
    # Use 4 decimal precision to match target output format (e.g., 62.7836)
    adjusted_rate = (base_rate * standard_hours) / total_hours
    return round(adjusted_rate, 4)


def get_employee_rate(employee_name: str, total_hours: float = 80.0) -> tuple:
    """
    Get the appropriate rate for an employee based on their type

    For salaried employees: Returns adjusted rate based on hours worked
    For hourly employees: Returns base rate

    Returns: (rate_to_use, base_rate, is_adjusted)
    """
    employees = load_employees()

    if employee_name not in employees:
        return (None, None, False)

    emp = employees[employee_name]
    base_rate = emp.base_rate

    if emp.is_salaried():
        adjusted_rate = calculate_adjusted_rate(base_rate, total_hours)
        is_adjusted = adjusted_rate != base_rate
        return (adjusted_rate, base_rate, is_adjusted)
    else:
        # Hourly employees use base rate
        return (base_rate, base_rate, False)


def is_employee_salaried(employee_name: str) -> Optional[bool]:
    """
    Check if an employee is salaried

    Returns: True if salaried, False if hourly, None if unknown
    """
    employees = load_employees()

    if employee_name not in employees:
        return None

    return employees[employee_name].is_salaried()


def validate_employees_against_paychex(paychex_names: List[str]) -> Dict:
    """
    Validate that all employees in Paychex data exist in master file

    Returns: {
        'valid': True/False,
        'matched': [...],      # Employees found in both
        'unknown': [...],      # In Paychex but not in master
        'missing': [...]       # In master but not in Paychex (not an error)
    }
    """
    employees = load_employees()
    master_names = set(employees.keys())
    paychex_set = set(paychex_names)

    matched = master_names.intersection(paychex_set)
    unknown = paychex_set - master_names
    missing = master_names - paychex_set

    return {
        'valid': len(unknown) == 0,
        'matched': list(matched),
        'unknown': list(unknown),
        'missing': list(missing)
    }


def bulk_update_employees(employees_data: List[Dict]) -> bool:
    """
    Update multiple employees at once (for roster approval workflow)

    employees_data: List of dicts with keys: name, employee_type, base_rate, etc.
    """
    employees = {}
    for emp_data in employees_data:
        employees[emp_data['name']] = Employee(
            name=emp_data['name'],
            employee_type=emp_data['employee_type'],
            base_rate=float(emp_data['base_rate']),
            qb_indirect_code=emp_data.get('qb_indirect_code', ''),
            qb_direct_code=emp_data.get('qb_direct_code', ''),
            paychex_name=emp_data.get('paychex_name', ''),
            is_owner=emp_data.get('is_owner', False)
        )
    return save_employees(employees)


# Initialize with default data if file doesn't exist
def initialize_default_employees():
    """
    Create default employees file from client spreadsheet data
    Only runs if employees.json doesn't exist
    """
    if os.path.exists(DEFAULT_EMPLOYEES_FILE):
        return

    # Default employee data from Rhea's 10-3-25 Employee Chart
    default_employees = {
        # Salaried Employees (9)
        "Amy C. Brown": Employee(
            name="Amy C. Brown",
            employee_type="salaried",
            base_rate=39.86,
            qb_indirect_code="Y - Indirect Employee Labor:AB",
            qb_direct_code="Y - Direct Employee Labor:Secretary III"
        ),
        "Gabrielle Demosthene": Employee(
            name="Gabrielle Demosthene",
            employee_type="salaried",
            base_rate=35.70,
            qb_indirect_code="Y - Indirect Employee Labor:GD",
            qb_direct_code="Y - Direct Employee Labor:Cost Analyst"
        ),
        "James R. Ferguson": Employee(
            name="James R. Ferguson",
            employee_type="salaried",
            base_rate=40.66,
            qb_indirect_code="Y - Indirect Employee Labor:JRF",
            qb_direct_code="Y - Direct Employee Labor:Geologist III"
        ),
        "Marcella J. Gallick": Employee(
            name="Marcella J. Gallick",
            employee_type="salaried",
            base_rate=67.36,
            qb_indirect_code="Y - Indirect Employee Labor:MG",
            qb_direct_code="Y - Direct Employee Labor:PM II"
        ),
        "Jeffrey Martinelli": Employee(
            name="Jeffrey Martinelli",
            employee_type="salaried",
            base_rate=41.84,
            qb_indirect_code="Y - Indirect Employee Labor:JM",
            qb_direct_code="Y - Direct Employee Labor:TMP Comm/Public Outreach Coord"
        ),
        "Brad A McCalla": Employee(
            name="Brad A McCalla",
            employee_type="salaried",
            base_rate=67.10,
            qb_indirect_code="Y - Indirect Employee Labor:BAM",
            qb_direct_code="Y - Direct Employee Labor:PM II"
        ),
        "Mark E. Scappe": Employee(
            name="Mark E. Scappe",
            employee_type="salaried",
            base_rate=61.32,
            qb_indirect_code="Y - Indirect Employee Labor:MES",
            qb_direct_code="Y - Direct Employee Labor:PM II"
        ),
        "Thomas R. Stahl": Employee(
            name="Thomas R. Stahl",
            employee_type="salaried",
            base_rate=55.04,
            qb_indirect_code="Y - Indirect Employee Labor:TRS",
            qb_direct_code="Y - Direct Employee Labor:Engineer IV"
        ),

        # Hourly Employees (14)
        "Roxanne K. Beall": Employee(
            name="Roxanne K. Beall",
            employee_type="hourly",
            base_rate=37.26,
            qb_indirect_code="Y - Indirect Employee Labor:RKB",
            qb_direct_code="Y - Direct Employee Labor:Assist. Proj. Mgr."
        ),
        "Monica L Blasko": Employee(
            name="Monica L Blasko",
            employee_type="hourly",
            base_rate=35.00,
            qb_indirect_code="Y - Indirect Employee Labor:MB",
            qb_direct_code="Y - Direct Employee Labor:Architectural Spec I"
        ),
        "Ann L. Clarke": Employee(
            name="Ann L. Clarke",
            employee_type="hourly",
            base_rate=68.18,
            qb_indirect_code="Y - Indirect Employee Labor:ALC",
            qb_direct_code="Y - Direct Employee Labor:Program Specialist I"
        ),
        "Lori A. Frye": Employee(
            name="Lori A. Frye",
            employee_type="hourly",
            base_rate=45.00,
            qb_indirect_code="Y - Indirect Employee Labor:LAF",
            qb_direct_code="Y - Direct Employee Labor:Archaeo. Tech."
        ),
        "Derek J. Horneman": Employee(
            name="Derek J. Horneman",
            employee_type="hourly",
            base_rate=35.00,
            qb_indirect_code="Y - Indirect Employee Labor:DJH",
            qb_direct_code="Y - Direct Employee Labor:Survey Crew Chief"
        ),
        "Nadia E Johnson": Employee(
            name="Nadia E Johnson",
            employee_type="hourly",
            base_rate=33.72,
            qb_indirect_code="Y - Indirect Employee Labor:NJ",
            qb_direct_code="Y - Direct Employee Labor:Archaeo. II"
        ),
        "Jeffrey A. Liebdzinski": Employee(
            name="Jeffrey A. Liebdzinski",
            employee_type="hourly",
            base_rate=39.34,
            qb_indirect_code="Y - Indirect Employee Labor:JAL",
            qb_direct_code="Y - Direct Employee Labor:Designer"
        ),
        "Marko Milojkovic": Employee(
            name="Marko Milojkovic",
            employee_type="hourly",
            base_rate=24.00,
            qb_indirect_code="Y - Indirect Employee Labor:MM",
            qb_direct_code="Y - Direct Employee Labor:Survey Technician"
        ),
        "Alyssa R Monaghan": Employee(
            name="Alyssa R Monaghan",
            employee_type="hourly",
            base_rate=34.00,
            qb_indirect_code="Y - Indirect Employee Labor:ARM",
            qb_direct_code="Y - Direct Employee Labor:Scientist II"
        ),
        "Megan E. Seivert": Employee(
            name="Megan E. Seivert",
            employee_type="hourly",
            base_rate=24.04,
            qb_indirect_code="Y - Indirect Employee Labor:Mseivert",
            qb_direct_code="Y - Direct Employee Labor:Secretary II"
        ),
        "Andrew B. Shaw": Employee(
            name="Andrew B. Shaw",
            employee_type="hourly",
            base_rate=25.00,
            qb_indirect_code="Y - Indirect Employee Labor:ABS",
            qb_direct_code="Y - Direct Employee Labor:Geo Spec I"
        ),
        "Thomas C. Smit": Employee(
            name="Thomas C. Smit",
            employee_type="hourly",
            base_rate=40.00,
            qb_indirect_code="Y - Indirect Employee Labor:TCS",
            qb_direct_code="Y - Direct Employee Labor:Chief of Surveys"
        ),
        "Liam J. Stubanas": Employee(
            name="Liam J. Stubanas",
            employee_type="hourly",
            base_rate=34.50,
            qb_indirect_code="Y - Indirect Employee Labor:LJS",
            qb_direct_code="Y - Direct Employee Labor:Engineering Spec II"
        ),
        "Lynn M Tomlinson": Employee(
            name="Lynn M Tomlinson",
            employee_type="hourly",
            base_rate=23.54,
            qb_indirect_code="Y - Indirect Employee Labor:LMT",
            qb_direct_code="Y - Direct Employee Labor:Secretary I"
        ),
    }

    save_employees(default_employees)
    print(f"Initialized default employees file: {DEFAULT_EMPLOYEES_FILE}")


# Auto-initialize on module import
initialize_default_employees()
