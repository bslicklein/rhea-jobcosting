# 🚀 Quick Start Guide - Job Costing Tool
## Get Started in 5 Minutes

---

## ✅ What You Have

1. **job_costing_converter.py** - The automation tool
2. **job_costing_output.xlsx** - Sample output showing what to expect
3. **README_Job_Costing_Tool.md** - Full documentation
4. **TECHNICAL_LOGIC_EXPLANATION.md** - Detailed calculation logic

---

## 🏃 Run Your First Job Costing in 3 Steps

### Step 1: Install Python Requirements
```bash
pip install pandas openpyxl
```

### Step 2: Export Your Paychex Files
- Export Week 1 payroll data from Paychex → Save as `week1.txt`
- Export Week 2 payroll data from Paychex → Save as `week2.txt`
- Put both files in the same folder as the Python script

### Step 3: Run the Tool
```bash
python job_costing_converter.py week1.txt week2.txt output.xlsx
```

**That's it!** Open `output.xlsx` to see your job costing summary.

---

## 📁 File Structure You Need

```
your_folder/
├── job_costing_converter.py    ← The tool
├── week1.txt                     ← Your Paychex Week 1 export
├── week2.txt                     ← Your Paychex Week 2 export
└── output.xlsx                   ← Generated automatically
```

---

## 🎯 What to Check in the Output

### Sheet 1: Job Costing Summary
✅ Look for your employees grouped by customer/project
✅ Verify regular hours + OT hours = total hours worked
✅ Check that OT only appears for weeks with >40 hours

### Sheet 2: Employee Totals  
✅ Confirm total hours match Paychex summaries
✅ Review which employees had overtime
✅ Verify total costs are reasonable

### Sheet 3: Detailed Records
✅ Use this for audit trail
✅ Spot-check a few entries against raw data
✅ Look at how OT was distributed across projects

---

## 🔍 Quick Validation Test

Pick one employee who had overtime:

1. **From Paychex:** Total hours worked that week
2. **From Tool Output:** Sum of Regular Hours + OT Hours for that employee
3. **Verify:** Both numbers should match exactly

**If they match → Tool is working correctly!**

---

## 💡 Pro Tips

### Tip 1: File Naming
Use date ranges in filenames for easy tracking:
```
paychex_2025-07-07_to_07-11.txt
paychex_2025-07-14_to_07-18.txt
job_costing_2025-07_biweekly.xlsx
```

### Tip 2: Archive Everything
Keep a folder structure like:
```
Job_Costing/
├── 2025/
│   ├── July/
│   │   ├── raw_paychex/
│   │   │   ├── week1.txt
│   │   │   └── week2.txt
│   │   └── output/
│   │       └── july_job_costing.xlsx
```

### Tip 3: Spot Check First
First time using the tool:
- Run it alongside your manual process once
- Compare the results carefully  
- Make sure you understand any differences
- Then trust it going forward!

### Tip 4: Handle Backlog Systematically
For your 2-3 month backlog (July-September):
1. Start with most recent (September)
2. Work backwards to July
3. Process one pay period at a time
4. Verify each before moving to next
5. Can clear entire backlog in 1-2 days!

---

## 🆘 Troubleshooting

### Error: "Cannot determine file format"
**Fix:** Make sure file ends in `.txt`, `.csv`, or `.xlsx`

### Error: "No module named 'pandas'"
**Fix:** Run `pip install pandas openpyxl`

### Numbers Don't Match Paychex
**Check:**
- Are you using the correct two weeks?
- Did both files import completely?
- Check the "Detailed Records" sheet for clues

### Employee Missing from Output
**Reason:** Employee had no time entries in those two weeks

### Overtime Seems Wrong
**Remember:** Tool distributes OT proportionally across all projects
- This is different from "last hours worked get OT"
- Both methods are valid; this one is more fair
- Can be customized if needed

---

## 📞 Getting Help

### For Tool Issues
1. Check error message in console
2. Review this Quick Start Guide
3. Consult the full README
4. Contact AuraPath support

### For Process Questions  
1. Review your old job costing documentation
2. Compare tool output to manual calculations
3. Identify specific differences
4. Request customization if needed

---

## 🎓 Understanding the Output

### What "Regular Hours" Means
Hours worked within the 40-hour threshold for the week, paid at standard rate.

### What "OT Hours" Means  
Hours worked over 40 in a week, paid at 1.5× rate. Distributed proportionally across all projects that week.

### What "Total Cost" Means
```
Total Cost = (Regular Hours × Rate) + (OT Hours × Rate × 1.5)
```

### Why OT Appears on All Projects
When someone works 42 hours across 5 projects:
- Total OT = 2 hours
- Each project gets a portion of those 2 hours
- Proportion based on time spent on that project
- This is FAIR allocation, not "last in gets OT"

---

## 📈 Success Metrics

After using this tool for one pay period, you should see:

✅ **Time Savings:** 6-8 hours → 30 minutes (90%+ reduction)
✅ **Accuracy:** Fewer data entry errors
✅ **Visibility:** Clear picture of where labor costs went
✅ **Audit Readiness:** Complete trail of calculations
✅ **Confidence:** Numbers match Paychex totals

---

## 🚦 Next Steps

### Immediate (This Week)
1. ✅ Run tool on most recent pay period
2. ✅ Validate output against manual calculation
3. ✅ Start processing backlog (Sept → July)

### Short Term (This Month)
1. Establish regular process using tool
2. Document any customization needs
3. Consider QuickBooks integration planning

### Long Term (Next Quarter)
1. Real-time dashboard development
2. Automated alerts for project cost overruns
3. Predictive cost forecasting

---

## 💪 You're Ready!

You now have everything you need to:
- ✅ Process job costing in 30 minutes instead of 6-8 hours
- ✅ Clear your 2-3 month backlog rapidly
- ✅ Get real-time visibility into project costs
- ✅ Maintain federal audit compliance
- ✅ Free up time for higher-value work

**Go ahead and run that first job costing. You've got this!** 🎯

---

**Questions?** Refer to the full README or contact AuraPath.

**Last Updated:** December 2, 2025
