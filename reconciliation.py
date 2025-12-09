"""
Reconciliation Module

Compares calculated job costing totals against Paychex payroll data
to ensure penny-perfect accuracy for federal audit compliance.

Rules:
- |difference| == $0.00: "reconciled" - perfect match
- |difference| <= $0.05: "adjusted" - auto-adjust to match (rounding tolerance)
- |difference| > $0.05: "check" - flag for manual review
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from paychex_parser import PaychexEmployee


@dataclass
class ReconciliationResult:
    """Result of reconciling a single employee's calculated vs Paychex totals."""
    employee_name: str

    # Wage comparison
    calculated_wages: float
    paychex_wages: float
    wages_difference: float

    # Hours comparison
    calculated_regular_hours: float
    calculated_ot_hours: float
    paychex_regular_hours: float
    paychex_ot_hours: float
    paychex_pto_hours: float
    paychex_holiday_hours: float

    # Status
    status: str  # "reconciled", "adjusted", "check"
    adjustment_applied: float  # Amount auto-adjusted (if any)

    # Rate info for salaried employees
    base_rate: Optional[float] = None
    adjusted_rate: Optional[float] = None
    is_rate_adjusted: bool = False

    @property
    def hours_match(self) -> bool:
        """Check if regular and OT hours match (within 0.5 hour tolerance)."""
        reg_diff = abs(self.calculated_regular_hours - self.paychex_regular_hours)
        ot_diff = abs(self.calculated_ot_hours - self.paychex_ot_hours)
        return reg_diff <= 0.5 and ot_diff <= 0.5

    @property
    def calculated_total_hours(self) -> float:
        """Total calculated hours."""
        return self.calculated_regular_hours + self.calculated_ot_hours

    @property
    def paychex_total_hours(self) -> float:
        """Total Paychex hours (all types)."""
        return (self.paychex_regular_hours + self.paychex_ot_hours +
                self.paychex_pto_hours + self.paychex_holiday_hours)


@dataclass
class ReconciliationReport:
    """Full reconciliation report for all employees."""
    results: List[ReconciliationResult]
    unmatched_qb: List[str]        # Employees in QB but not Paychex
    unmatched_paychex: List[str]   # Employees in Paychex but not QB

    @property
    def total_reconciled(self) -> int:
        """Count of perfectly reconciled employees."""
        return sum(1 for r in self.results if r.status == 'reconciled')

    @property
    def total_adjusted(self) -> int:
        """Count of auto-adjusted employees (within tolerance)."""
        return sum(1 for r in self.results if r.status == 'adjusted')

    @property
    def total_check(self) -> int:
        """Count of employees flagged for review."""
        return sum(1 for r in self.results if r.status == 'check')

    @property
    def total_calculated(self) -> float:
        """Sum of all calculated wages."""
        return sum(r.calculated_wages for r in self.results)

    @property
    def total_paychex(self) -> float:
        """Sum of all Paychex gross wages."""
        return sum(r.paychex_wages for r in self.results)

    @property
    def overall_difference(self) -> float:
        """Overall difference between calculated and Paychex."""
        return self.total_calculated - self.total_paychex


def reconcile_employee(
    employee_name: str,
    calculated_wages: float,
    calculated_regular_hours: float,
    calculated_ot_hours: float,
    paychex_data: Optional[PaychexEmployee],
    tolerance: float = 0.05,
    base_rate: Optional[float] = None,
    adjusted_rate: Optional[float] = None
) -> ReconciliationResult:
    """
    Reconcile a single employee's calculated totals against Paychex data.

    Args:
        employee_name: Employee name from QuickBooks
        calculated_wages: Total calculated wages from job costing
        calculated_regular_hours: Calculated regular hours
        calculated_ot_hours: Calculated OT hours
        paychex_data: PaychexEmployee record (or None if no match)
        tolerance: Maximum acceptable difference for auto-adjustment ($0.05 default)
        base_rate: Original base rate (for salaried employees)
        adjusted_rate: Adjusted rate (for salaried who worked != 80 hours)

    Returns:
        ReconciliationResult with comparison and status
    """
    if paychex_data is None:
        # No Paychex data - can't reconcile
        return ReconciliationResult(
            employee_name=employee_name,
            calculated_wages=calculated_wages,
            paychex_wages=0.0,
            wages_difference=calculated_wages,
            calculated_regular_hours=calculated_regular_hours,
            calculated_ot_hours=calculated_ot_hours,
            paychex_regular_hours=0.0,
            paychex_ot_hours=0.0,
            paychex_pto_hours=0.0,
            paychex_holiday_hours=0.0,
            status='check',
            adjustment_applied=0.0,
            base_rate=base_rate,
            adjusted_rate=adjusted_rate,
            is_rate_adjusted=(base_rate != adjusted_rate) if base_rate and adjusted_rate else False
        )

    # Calculate difference
    paychex_wages = paychex_data.gross_wages
    difference = round(calculated_wages - paychex_wages, 2)
    abs_diff = abs(difference)

    # Determine status
    if abs_diff == 0:
        status = 'reconciled'
        adjustment = 0.0
    elif abs_diff <= tolerance:
        status = 'adjusted'
        adjustment = -difference  # Amount to add to make it match
    else:
        status = 'check'
        adjustment = 0.0

    return ReconciliationResult(
        employee_name=employee_name,
        calculated_wages=calculated_wages,
        paychex_wages=paychex_wages,
        wages_difference=difference,
        calculated_regular_hours=calculated_regular_hours,
        calculated_ot_hours=calculated_ot_hours,
        paychex_regular_hours=paychex_data.regular_hours,
        paychex_ot_hours=paychex_data.ot_hours,
        paychex_pto_hours=paychex_data.pto_hours,
        paychex_holiday_hours=paychex_data.holiday_hours,
        status=status,
        adjustment_applied=adjustment,
        base_rate=base_rate,
        adjusted_rate=adjusted_rate,
        is_rate_adjusted=(base_rate != adjusted_rate) if base_rate and adjusted_rate else False
    )


def generate_reconciliation_report(
    employee_totals: Dict[str, dict],
    paychex_match_results: Dict[str, PaychexEmployee],
    unmatched_qb: List[str],
    unmatched_paychex: List[str],
    tolerance: float = 0.05
) -> ReconciliationReport:
    """
    Generate a full reconciliation report for all employees.

    Args:
        employee_totals: Dict mapping employee name -> {
            'total_cost': float,
            'regular_hours': float,
            'ot_hours': float,
            'base_rate': float (optional),
            'adjusted_rate': float (optional)
        }
        paychex_match_results: Dict mapping QB employee name -> PaychexEmployee
        unmatched_qb: List of QB employees not matched to Paychex
        unmatched_paychex: List of Paychex employees not matched to QB
        tolerance: Maximum acceptable difference for auto-adjustment

    Returns:
        ReconciliationReport with all results
    """
    results = []

    for emp_name, totals in employee_totals.items():
        paychex_emp = paychex_match_results.get(emp_name)

        result = reconcile_employee(
            employee_name=emp_name,
            calculated_wages=totals.get('total_cost', 0.0),
            calculated_regular_hours=totals.get('regular_hours', 0.0),
            calculated_ot_hours=totals.get('ot_hours', 0.0),
            paychex_data=paychex_emp,
            tolerance=tolerance,
            base_rate=totals.get('base_rate'),
            adjusted_rate=totals.get('adjusted_rate')
        )
        results.append(result)

    # Sort by status priority: check first, then adjusted, then reconciled
    status_order = {'check': 0, 'adjusted': 1, 'reconciled': 2}
    results.sort(key=lambda r: (status_order.get(r.status, 3), r.employee_name))

    return ReconciliationReport(
        results=results,
        unmatched_qb=unmatched_qb,
        unmatched_paychex=unmatched_paychex
    )


def format_status_emoji(status: str) -> str:
    """Get emoji/symbol for reconciliation status."""
    return {
        'reconciled': '✓ Reconciled',
        'adjusted': '⚡ Adjusted',
        'check': '⚠️ CHECK'
    }.get(status, status)


def format_rate_note(base_rate: Optional[float], adjusted_rate: Optional[float], total_hours: float) -> str:
    """
    Format rate adjustment note for salaried employees.

    Example: "Base $67.10 adj to $62.78 (85.5 hrs)"
    """
    if not base_rate or not adjusted_rate:
        return ""

    if abs(base_rate - adjusted_rate) < 0.01:
        return ""  # No adjustment

    return f"Base ${base_rate:.2f} adj to ${adjusted_rate:.2f} ({total_hours:.1f} hrs)"


def get_reconciliation_summary(report: ReconciliationReport) -> dict:
    """
    Generate a summary dict of the reconciliation report for API response.
    """
    return {
        'total_employees': len(report.results),
        'reconciled': report.total_reconciled,
        'adjusted': report.total_adjusted,
        'needs_review': report.total_check,
        'unmatched_qb': len(report.unmatched_qb),
        'unmatched_paychex': len(report.unmatched_paychex),
        'total_calculated': round(report.total_calculated, 2),
        'total_paychex': round(report.total_paychex, 2),
        'overall_difference': round(report.overall_difference, 2),
        'results': [
            {
                'employee': r.employee_name,
                'calculated': round(r.calculated_wages, 2),
                'paychex': round(r.paychex_wages, 2),
                'difference': round(r.wages_difference, 2),
                'status': r.status,
                'status_display': format_status_emoji(r.status),
                'hours_match': bool(r.hours_match),
                'calculated_hours': round(r.calculated_total_hours, 2),
                'paychex_hours': round(r.paychex_total_hours, 2),
                'rate_note': format_rate_note(r.base_rate, r.adjusted_rate, r.calculated_total_hours)
            }
            for r in report.results
        ],
        'unmatched_qb_names': report.unmatched_qb,
        'unmatched_paychex_names': report.unmatched_paychex
    }
