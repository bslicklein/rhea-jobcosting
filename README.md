# Rhea Job Costing Tool

Automates bi-weekly job costing for Rhea Engineering. Converts QuickBooks payroll exports into job costing summaries with proper overtime calculations.

**Time Savings:** 6-8 hours → 30 minutes per pay period

---

## Quick Start

### 1. Start the Web App

```bash
./start_webapp.sh
```

Then open **http://127.0.0.1:5000** in your browser.

### 2. Manual Start (if needed)

```bash
source venv/bin/activate
python app.py
```

### 3. First-Time Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## How to Use

### Step 1: Review Employee Roster
The app shows your employee roster first. Verify rates and employee types (hourly/salaried) are correct.

### Step 2: Upload QuickBooks Files
- Upload **Week 1** QuickBooks export (.xlsx)
- Upload **Week 2** QuickBooks export (.xlsx)
- Optionally upload **Paychex** file for reconciliation

### Step 3: Handle Overtime (if needed)
For hourly employees with >40 hours, you'll select which job receives the overtime hours.

### Step 4: Download Results
Click "Download Excel File" to get your job costing output.

---

## File Requirements

QuickBooks exports need these columns:
- Activity date
- Customer full name
- Duration (HH:MM format)
- Rates
- Description
- Billable (Y/N)

---

## Key Business Rules

| Rule | Description |
|------|-------------|
| **Hourly OT** | >40 hours/week = overtime at 1.5× rate |
| **Salaried Adjustment** | >80 hours/pay period = reduced effective rate |
| **Penny-Perfect Totals** | Salaried employee amounts sum exactly to base_rate × 80 |

---

## Troubleshooting

### Port Already in Use
```bash
lsof -ti:5000 | xargs kill -9
```

### Dependencies Not Found
```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Numbers Don't Match
- Verify correct Week 1/Week 2 files
- Check employee roster rates
- Review "Detailed Records" in output Excel

---

## Project Structure

```
rhea-jobcosting/
├── app.py                    # Flask web server
├── job_costing_converter.py  # Core processing logic
├── employee_master.py        # Employee data management
├── paychex_parser.py         # Paychex file parser
├── reconciliation.py         # Reconciliation logic
├── templates/
│   └── index.html            # Web interface
├── employees.json            # Employee database
├── requirements.txt          # Python dependencies
├── start_webapp.sh           # Startup script
├── README.md                 # This file
├── TECHNICAL_DOCS.md         # Detailed technical reference
└── CLAUDE.md                 # AI assistant context
```

---

## Support

For questions or issues, contact AuraPath support.

**Last Updated:** December 2025
