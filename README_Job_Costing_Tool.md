# Job Costing Automation Tool - Proof of Concept
## Rhea Engineering - AuraPath Implementation

---

## 🎯 Purpose

This tool automates the bi-weekly job costing process described in the Rhea Engineering Discovery Report. It converts Paychex payroll data (two weekly files) into a comprehensive job costing summary that:

- Groups hours by employee and customer/project
- Separates regular hours from overtime hours
- Calculates costs including overtime multipliers (1.5x)
- Provides audit trail with detailed records
- **Reduces processing time from 6-8 hours to under 30 minutes**

---

## 📊 What This Tool Does

### Input
- Two tab-delimited text files or Excel files from Paychex (Week 1 and Week 2 of pay period)
- Each file contains employee time entries with:
  - Activity date
  - Customer/project name
  - Duration (HH:MM format)
  - Hourly rate (for billable work)

### Processing
1. **Parses Duration** - Converts HH:MM format to decimal hours
2. **Identifies Overtime** - Calculates hours over 40 per week per employee
3. **Allocates OT Proportionally** - Distributes overtime hours across projects
4. **Calculates Costs** - Applies regular and overtime (1.5x) rates
5. **Groups by Employee & Customer** - Summarizes all work by project

### Output (Excel file with 3 sheets)
1. **Job Costing Summary** - Employee → Customer groupings with regular/OT hours and costs
2. **Employee Totals** - Summary totals for each employee
3. **Detailed Records** - Complete audit trail of all calculations

---

## 🚀 How to Use

### Quick Start (Command Line)

```bash
python job_costing_converter.py week1_file.txt week2_file.txt output.xlsx
```

**Example:**
```bash
python job_costing_converter.py paychex_week1.txt paychex_week2.txt july_job_costing.xlsx
```

### Arguments
- **Argument 1:** Path to Week 1 file (.txt, .csv, or .xlsx)
- **Argument 2:** Path to Week 2 file (.txt, .csv, or .xlsx)
- **Argument 3 (optional):** Output filename (default: job_costing_output.xlsx)

### File Format Requirements
The tool expects Paychex export format with these columns:
- Activity date
- Customer full name
- Product/Service full name
- Description
- Rates
- Duration (HH:MM format)
- Billable (Y/N)
- Amount

---

## 📋 Sample Output

### Employee Totals Example:
```
Employee Name      Regular Hours   OT Hours   Regular Cost   OT Cost    Total Cost
Amy C. Brown       80.01          0.49       $8,000.01      $75.00     $8,075.01
Andrew B. Shaw     80.00          0.00       $6,400.00      $0.00      $6,400.00
```

### Job Costing Summary (by Customer):
```
Employee         Customer/Project                          Reg Hrs   OT Hrs   Rate   Total Cost
Amy C. Brown     Rhea:802 G&A Indirect Labor:Accounting    56.13     0.37     $100   $5,668.52
Andrew B. Shaw   GPI:2506 - Hatchery Rehab:Hatch House     15.00     0.00     $80    $1,200.00
```

---

## 🔍 Key Features

### 1. Overtime Detection & Calculation
- Automatically identifies when employees exceed 40 hours per week
- Calculates overtime at 1.5x rate
- Proportionally allocates OT hours across projects

### 2. Flexible File Handling
- Accepts .txt, .csv, or .xlsx files
- Handles tab-delimited or Excel formats
- Automatically detects employee name rows

### 3. Comprehensive Output
- Summary view for management reporting
- Detailed audit trail for federal compliance
- Easy-to-read Excel format with proper formatting

### 4. Error Handling
- Validates file format
- Handles missing data gracefully
- Provides clear error messages

---

## 💡 Current Limitations & Next Steps

### Current POC Limitations:
1. **OT Allocation Logic** - Uses simple proportional allocation
   - Real system needs rules for: holidays, approved straight-time OT, vacation
   
2. **Manual File Upload** - Still requires manually downloading from Paychex
   - Next: Direct QuickBooks integration
   
3. **Salaried Employee Logic** - Needs additional rules for >80 hours in 2 weeks
   - POC handles hourly OT, but salaried calculations need refinement

4. **No Dashboard** - Outputs Excel file only
   - Next: Real-time web dashboard showing project costs vs. bids

### Production Roadmap:

#### Phase 1: Core Automation (Month 1)
- [x] POC tool development
- [ ] QuickBooks API integration (eliminate manual export)
- [ ] Enhanced OT allocation rules
- [ ] Salaried employee rate adjustments
- [ ] Automated backlog processing (July-September)

#### Phase 2: Intelligence Layer (Month 2)
- [ ] Real-time project cost dashboard
- [ ] Variance alerts (actual vs. bid)
- [ ] Predictive project cost forecasting
- [ ] Automated audit compliance reporting

#### Phase 3: Integration (Month 3)
- [ ] Email notifications for cost overruns
- [ ] Integration with billing system
- [ ] Automated monthly/quarterly reports
- [ ] Mobile dashboard access

---

## 📈 Expected Impact (from Discovery Report)

### Time Savings
- **Current process:** 6-8 hours per bi-weekly cycle
- **With automation:** <30 minutes per cycle
- **Annual savings:** 156-208 hours = $7,800-$10,400

### Business Impact
- **Backlog elimination:** Clear 2-3 month backlog within 30 days
- **Real-time visibility:** Project profitability visible immediately (vs. 6-12 week lag)
- **Audit readiness:** Automated compliance documentation
- **Cash flow:** Faster billing on cost-reimbursable contracts

### Cost Savings
- Replaces portion of $80K-$100K HR Director role
- Frees Lynn to focus on AR and higher-value accounting work
- Reduces Marcy's time on operational tasks → more time for business development

---

## 🔧 Technical Requirements

### Python Dependencies
```bash
pip install pandas openpyxl
```

### Minimum System Requirements
- Python 3.8+
- 100MB free disk space
- Works on Windows, Mac, Linux

---

## 📝 Usage Tips

1. **File Naming Convention**
   ```
   paychex_2025-07-07_to_07-11.txt  (Week 1)
   paychex_2025-07-14_to_07-18.txt  (Week 2)
   ```

2. **Verify Output**
   - Always check employee totals match Paychex summary
   - Review OT allocation for employees with >40 hours
   - Spot-check a few customer totals against detailed records

3. **Archive Files**
   - Keep raw Paychex files for audit trail
   - Archive output Excel files by pay period
   - Document any manual adjustments in Notes column

---

## 🆘 Support & Questions

For questions about this POC tool:
- **AuraPath Support:** [contact info]
- **Technical Issues:** Check error messages in console output
- **Enhancement Requests:** Document and include in Phase 1 scope

---

## 📄 Related Documents

- **Discovery Report:** `Rhea-Engineering-Discovery-Report.docx`
- **Sample Input:** `paychex_week1.txt`, `paychex_week2.txt`
- **Sample Output:** `job_costing_output.xlsx`

---

**Last Updated:** December 2, 2025
**Version:** 1.0 (Proof of Concept)
**Status:** Ready for testing with real Paychex data

---

## 🎓 How This Solves the Problem

From the Discovery Report, the job costing process had these pain points:

✅ **Manual Data Transfer** → Automated parsing and import
✅ **Complex OT Calculations** → Intelligent rule-based allocation  
✅ **2-3 Month Backlog** → 95% time reduction enables rapid catch-up
✅ **No Real-Time Visibility** → Foundation for dashboard (Phase 2)
✅ **Labor-Intensive Process** → 6-8 hours → 30 minutes

This POC proves the technical feasibility. The next step is production implementation with QuickBooks integration and the full intelligence layer.
