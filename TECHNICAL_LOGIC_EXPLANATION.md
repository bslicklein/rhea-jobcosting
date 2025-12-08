# Job Costing Conversion Logic - Technical Explanation
## Understanding the "Mental Math" Behind the Tool

---

## 🧮 Overview

This document explains the exact calculations and logic the job costing tool performs. This helps you understand, verify, and potentially customize the tool for Rhea Engineering's specific requirements.

---

## 📊 Step-by-Step Processing Logic

### Step 1: Parse Duration to Decimal Hours

**Input Format:** `HH:MM` (e.g., "03:30")
**Output:** Decimal hours (e.g., 3.5)

**Formula:**
```
decimal_hours = hours + (minutes / 60)
```

**Examples:**
- `01:30` → 1.5 hours
- `08:15` → 8.25 hours
- `00:45` → 0.75 hours

**Why:** All calculations need consistent decimal format for math operations.

---

### Step 2: Identify Employee Names

**Logic:**
- Scan through file looking for rows where Activity Date is empty but first column has text
- These rows contain employee names (e.g., "Amy C. Brown")
- Skip "Total for..." rows
- Assign each subsequent data row to the most recent employee name

**Why:** Paychex format groups entries by employee with name as a header row.

---

### Step 3: Calculate Weekly Hours per Employee

**For Each Employee:**
```
Week 1 Total = Sum of all hours in Week 1 for that employee
Week 2 Total = Sum of all hours in Week 2 for that employee
```

**Example - Amy C. Brown:**
```
Week 1: 
  0.5 + 5.5 + 1.0 + 1.0 + 1.0 + ... = 40.5 hours

Week 2:
  2.0 + 1.0 + 4.0 + 1.0 + 3.0 + ... = 40.0 hours
```

**Why:** Need weekly totals to determine if overtime occurred.

---

### Step 4: Determine Overtime Status

**Rule:** If weekly hours > 40, employee has overtime for that week

**Example:**
```
Amy Week 1: 40.5 hours → HAS OVERTIME (0.5 hours)
Amy Week 2: 40.0 hours → NO OVERTIME
Andrew Week 1: 40.0 hours → NO OVERTIME
Andrew Week 2: 40.0 hours → NO OVERTIME
```

**Why:** Federal labor law requires overtime pay for hourly employees working >40 hours/week.

---

### Step 5: Allocate Overtime Proportionally

This is the most complex calculation. Here's the detailed logic:

**For weeks WITHOUT overtime:**
```
Regular Hours = All hours
OT Hours = 0
```

**For weeks WITH overtime:**

The tool distributes OT hours proportionally across all projects based on how much time was spent on each.

**Formula:**
```
Total OT Hours for Week = Weekly Hours - 40
Proportion for This Entry = Entry Hours / Total Weekly Hours
OT Hours for This Entry = Total OT Hours × Proportion
Regular Hours for This Entry = Entry Hours - OT Hours for This Entry
```

**Example - Amy Week 1 (40.5 total hours, 0.5 OT):**

Entry #1: Banking/Credit (0.5 hours)
```
Proportion = 0.5 / 40.5 = 0.01234568 (1.23%)
OT Hours = 0.5 × 0.01234568 = 0.006173 hours
Regular Hours = 0.5 - 0.006173 = 0.493827 hours
```

Entry #2: Accounting (5.5 hours)  
```
Proportion = 5.5 / 40.5 = 0.13580247 (13.58%)
OT Hours = 0.5 × 0.13580247 = 0.067901 hours
Regular Hours = 5.5 - 0.067901 = 5.432099 hours
```

**Why:** This ensures total OT equals exactly 0.5 hours, distributed fairly across all work.

---

### Step 6: Extract Employee Hourly Rate

**Logic:**
- Find the first billable entry for each employee
- Extract the rate from the "Rates" column
- Use this rate for all calculations for that employee

**Example:**
- Amy C. Brown: First billable entry shows $100/hour → Use $100 for all calculations
- Andrew B. Shaw: First billable entry shows $80/hour → Use $80 for all calculations

**Why:** Need consistent rate for cost calculations. Billable rates are typically the employee's standard rate.

**Note for Production:** May need refinement for:
- Salaried employees (rate derived differently)
- Employees with multiple rates
- Indirect labor without explicit rates

---

### Step 7: Calculate Costs

**Formulas:**

**Regular Cost:**
```
Regular Cost = Regular Hours × Hourly Rate
```

**Overtime Cost:**
```
OT Cost = OT Hours × Hourly Rate × 1.5
```

**Total Cost:**
```
Total Cost = Regular Cost + OT Cost
```

**Example - Amy Banking Entry (0.493827 reg hrs, 0.006173 OT hrs, $100/hr):**
```
Regular Cost = 0.493827 × $100 = $49.38
OT Cost = 0.006173 × $100 × 1.5 = $0.93
Total Cost = $49.38 + $0.93 = $50.31
```

**Why:** Overtime must be paid at 1.5× (time-and-a-half) per federal law.

---

### Step 8: Group by Employee and Customer

**Logic:**
- Combine all entries for same Employee + Customer combination
- Sum: Regular Hours, OT Hours, Regular Cost, OT Cost, Total Cost
- Sort by: Employee Name (A→Z), then Customer Name (A→Z)

**Example - Andrew's GPI:2506 entries:**

Entry 1 (Week 1): 3.5 hours @ $80 = $280
Entry 2 (Week 1): 4.0 hours @ $80 = $320
Entry 3 (Week 1): 1.5 hours @ $80 = $120
... (more entries)

**Grouped Result:**
```
Andrew B. Shaw | GPI:2506 - Pleasant Mount Hatchery Rehab:250603 - Hatch House #2
Regular Hours: 15.0
OT Hours: 0.0
Total Cost: $1,200
```

**Why:** Management needs to see total time/cost per project, not individual daily entries.

---

## 🎯 Special Cases & Edge Cases

### Case 1: No Overtime
**Scenario:** Employee works exactly 40 hours or less
**Handling:** All hours are regular, OT Hours = 0, no 1.5× multiplier

### Case 2: Multiple Customers in OT Week  
**Scenario:** Employee has OT but worked on 10 different projects
**Handling:** OT is distributed proportionally across all 10 projects

### Case 3: Non-Billable Work
**Scenario:** Internal overhead, meetings, administrative time
**Handling:** No rate in Rates column → Tool uses the employee's standard rate from their first billable entry

### Case 4: Different Rates
**Scenario:** Employee has different rates for different projects (not in current POC)
**Handling:** Production version needs to track rate per project type

### Case 5: Salaried Employees (Future Enhancement)
**Scenario:** Salaried employee works >80 hours in 2-week period
**Special Rule:** Effective hourly rate is reduced (not increased like OT)
**Formula:** 
```
Effective Rate = (Bi-weekly Salary) / (Actual Hours Worked)
```
Example: $3,000 salary ÷ 90 hours = $33.33/hour (vs. normal $37.50/hour)

**Why:** Salaried employees don't get overtime pay; instead, their cost per hour decreases as they work more.

---

## 📋 Validation Checklist

After running the tool, verify these calculations:

### ✅ Week Hour Totals
```
For each employee:
  Week 1 Total (from tool) = Sum of all Week 1 durations
  Week 2 Total (from tool) = Sum of all Week 2 durations
```

### ✅ Overtime Threshold
```
If Weekly Hours ≤ 40 → All Regular Hours, Zero OT Hours
If Weekly Hours > 40 → Some OT Hours = (Weekly Hours - 40)
```

### ✅ Total Hours Conservation
```
For each employee:
  Sum of (Regular Hours + OT Hours) across all customers 
  = Total bi-weekly hours worked
```

### ✅ OT Hour Totals
```
For each week with OT:
  Sum of all OT Hours across all projects
  = (Weekly Hours - 40)
```

### ✅ Cost Calculations
```
Pick any entry:
  Regular Cost = Regular Hours × Rate (should match)
  OT Cost = OT Hours × Rate × 1.5 (should match)
  Total = Regular + OT (should match)
```

---

## 🔧 Customization Points

If Rhea Engineering needs to modify the logic, these are the key functions to adjust:

### 1. Overtime Allocation (`calculate_regular_and_ot_hours`)
**Current:** Proportional distribution
**Customize for:**
- Specific projects get OT first
- Holiday/vacation OT treated differently
- Pre-approved straight-time OT

### 2. Rate Determination (`employee_rates` lookup)
**Current:** Use first billable rate found
**Customize for:**
- Salaried employees (fixed rate or calculated from salary)
- Project-specific rates
- Labor category rates

### 3. Week Boundary Detection
**Current:** Simple Week 1 vs. Week 2 flag
**Customize for:**
- Specific pay period dates
- Holiday weeks
- Partial weeks

### 4. Grouping Level (`groupby` operations)
**Current:** Employee + Customer full name
**Customize for:**
- Different project hierarchy levels
- Department-level rollups
- Cost center allocations

---

## 📊 Sample Calculation Walkthrough

Let's trace one complete example through all steps:

**Raw Data Entry:**
```
Employee: Amy C. Brown
Date: 07/14/2025  
Customer: Rhea:802 G&A Indirect Labor:80204 Accounting/Tax Mgmt.
Duration: 05:30
Rate: $100
Week: 1
Weekly Total: 40.5 hours
```

**Step-by-Step:**

1. **Parse Duration:** 05:30 → 5.5 hours

2. **Identify Week Total:** Amy Week 1 = 40.5 hours → Has OT (0.5 hours)

3. **Calculate Proportion:** 5.5 / 40.5 = 0.135802

4. **Allocate OT:** 
   - OT Hours = 0.5 × 0.135802 = 0.067901
   - Regular Hours = 5.5 - 0.067901 = 5.432099

5. **Calculate Costs:**
   - Regular Cost = 5.432099 × $100 = $543.21
   - OT Cost = 0.067901 × $100 × 1.5 = $10.19
   - Total Cost = $543.21 + $10.19 = $553.40

**Result in Output:**
```
Employee: Amy C. Brown
Customer: Rhea:802 G&A Indirect Labor:80204 Accounting/Tax Mgmt.
Regular Hours: 5.43 (rounded for display)
OT Hours: 0.07 (rounded for display)
Total Cost: $553.40
```

---

## 🚨 Important Notes

### Federal Compliance
- 40-hour threshold is federal standard for hourly employees
- 1.5× multiplier is federal minimum for overtime
- Some states have additional requirements (e.g., daily OT after 8 hours)
- Government contracts often have specific rules

### Rounding
- Tool uses full precision in calculations
- Only rounds for display in Excel (2 decimal places)
- Avoids rounding errors by summing precise values first

### Audit Trail
- Detailed Records sheet shows every calculation
- Can trace any summary number back to source data
- Preserves data for federal audits

---

## 📈 Next Steps for Production

1. **Validate Logic** - Run POC alongside manual process for 1-2 cycles
2. **Refine Rules** - Add company-specific OT allocation rules
3. **Add Salaried Logic** - Implement >80 hour rate reduction
4. **QuickBooks Integration** - Eliminate manual file export/import
5. **Dashboard Development** - Real-time visibility into project costs

---

**Questions about these calculations?** 
Contact AuraPath for clarification or customization assistance.

---

**Last Updated:** December 2, 2025
**Version:** 1.0 (POC)
