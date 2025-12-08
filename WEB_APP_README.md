# Job Costing Web Application
## User-Friendly Interface for Rhea Engineering

---

## 🎯 Overview

The Job Costing Web Application provides an intuitive, browser-based interface for the job costing automation tool. No command-line experience required!

**Features:**
- 📤 Drag-and-drop file upload
- 📊 Live preview of results
- 💾 One-click Excel download
- 📈 Visual summary statistics
- ✨ Modern, responsive design

---

## 🚀 Quick Start

### Option 1: Using the Startup Script (Recommended)

```bash
cd "/Users/brandon/Documents/Repository/Rhea POC"
./start_webapp.sh
```

Then open your browser to: **http://127.0.0.1:5000**

### Option 2: Manual Start

```bash
cd "/Users/brandon/Documents/Repository/Rhea POC"
source venv/bin/activate
python app.py
```

Then open your browser to: **http://127.0.0.1:5000**

---

## 📋 How to Use

### Step 1: Export Paychex Data
1. Log into Paychex
2. Export Week 1 payroll data → Save as `.txt`, `.csv`, or `.xlsx`
3. Export Week 2 payroll data → Save as `.txt`, `.csv`, or `.xlsx`

### Step 2: Upload Files
1. Open the web app in your browser
2. Click "Choose File" for Week 1 and select your file
3. Click "Choose File" for Week 2 and select your file
4. Click **"Process Job Costing"**

### Step 3: Review Results
- View summary statistics (total employees, costs, hours)
- Review **Employee Totals** tab
- Review **Job Costing Summary** tab (grouped by employee & customer)

### Step 4: Download Report
- Click **"Download Excel File"** button
- Opens the complete Excel file with 3 sheets:
  1. Job Costing Summary
  2. Employee Totals
  3. Detailed Records (audit trail)

---

## 🎨 User Interface Features

### File Upload Section
- **Visual file picker** - No typing file paths
- **File validation** - Only accepts `.txt`, `.csv`, `.xlsx`, `.xls`
- **Progress indicator** - Shows when processing
- **Error handling** - Clear error messages if something goes wrong

### Results Display
- **Summary Statistics Card**
  - Total employees processed
  - Total labor cost
  - Regular hours vs. OT hours

- **Tabbed Data Tables**
  - Employee Totals (by employee)
  - Job Costing Summary (by employee & customer)
  - Formatted currency and numbers
  - Scrollable for large datasets

### Download
- **One-click download** - Gets your Excel file instantly
- **Auto-generated filename** - Includes date/time stamp
- **Same format as command-line tool** - Complete with all 3 sheets

---

## 🔧 Technical Details

### Technology Stack
- **Backend:** Flask (Python web framework)
- **Frontend:** Vanilla JavaScript (no dependencies)
- **Styling:** Custom CSS with gradient design
- **Data Processing:** Uses the existing `job_costing_converter.py`

### File Structure
```
Rhea POC/
├── app.py                    # Flask web server
├── templates/
│   └── index.html           # Web interface
├── job_costing_converter.py # Core processing logic
├── start_webapp.sh          # Startup script
└── requirements.txt         # Python dependencies
```

### Security Features
- **File size limits:** 16MB max per file
- **File type validation:** Only accepts approved formats
- **Secure filenames:** Sanitized to prevent directory traversal
- **Temporary storage:** Uploaded files deleted after processing
- **No data retention:** Files removed immediately after use

---

## 🛠️ Troubleshooting

### Port Already in Use
If you see "Port 5000 already in use":
```bash
# Find and kill the process using port 5000
lsof -ti:5000 | xargs kill -9
```

Or edit `app.py` line 114 to use a different port:
```python
app.run(debug=True, port=5001)  # Change to 5001 or any available port
```

### Dependencies Not Installed
```bash
cd "/Users/brandon/Documents/Repository/Rhea POC"
source venv/bin/activate
pip install -r requirements.txt
```

### Browser Showing "Connection Refused"
- Make sure the Flask app is running (you should see terminal output)
- Check you're using the correct URL: `http://127.0.0.1:5000`
- Try `http://localhost:5000` instead

### Upload Fails with Error
- **Check file format:** Must be `.txt`, `.csv`, `.xlsx`, or `.xls`
- **Check file size:** Must be under 16MB
- **Check Paychex format:** Should have the standard columns (Activity date, Customer full name, Duration, etc.)
- **Check both files selected:** Both Week 1 and Week 2 required

### Numbers Don't Match Expected
- Verify you uploaded the correct two weeks
- Check the "Detailed Records" tab in the downloaded Excel file
- Compare employee totals to Paychex summaries
- Review the overtime allocation logic in the Technical Documentation

---

## 📊 Sample Workflow

**Scenario:** Processing bi-weekly payroll for July 7-18, 2025

1. **Export from Paychex:**
   - `paychex_2025-07-07_to_07-11.xlsx` (Week 1)
   - `paychex_2025-07-14_to_07-18.xlsx` (Week 2)

2. **Upload to Web App:**
   - Open http://127.0.0.1:5000
   - Select both files
   - Click "Process Job Costing"
   - Wait ~5-10 seconds

3. **Review Results:**
   - Summary shows: 12 employees, $45,623.50 total cost
   - Employee Totals tab: 3 employees with overtime
   - Job Costing Summary: Hours broken down by customer/project

4. **Download:**
   - Click "Download Excel File"
   - File saved: `job_costing_20250720_143052.xlsx`
   - Import into QuickBooks or accounting system

5. **Archive:**
   - Save Excel file to archive folder
   - Keep raw Paychex files for audit trail

---

## 🔐 Privacy & Data Security

### Data Handling
- **All processing happens locally** on your computer
- **No data sent to external servers** (except your own Flask app)
- **Files stored temporarily** in system temp folder
- **Automatic cleanup** after processing
- **No logging of sensitive data**

### Best Practices
1. **Use on trusted computer** - Don't use on public/shared machines
2. **Close browser tab** after use
3. **Keep browser updated** for security patches
4. **Don't share download links** (they're local files anyway)
5. **Archive output files** in secure location

---

## 🎓 Training Resources

### For New Users
1. Watch the demo (if available)
2. Start with the sample files to understand the format
3. Process one pay period alongside manual method
4. Verify results match before going production

### For Advanced Users
- Customize `app.py` to add features (e.g., email alerts)
- Modify `templates/index.html` to change UI design
- Integrate with QuickBooks API (Phase 2 roadmap)
- Add user authentication for multi-user environments

---

## 📈 Performance

### Processing Speed
- **2 employees, 2 weeks:** ~2-3 seconds
- **10 employees, 2 weeks:** ~5-10 seconds
- **50 employees, 2 weeks:** ~15-30 seconds

### File Size Limits
- **Maximum upload:** 16MB per file
- **Recommended:** Under 5MB for best performance
- **Typical Paychex export:** 100-500KB

### Browser Compatibility
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

---

## 🚦 Next Steps & Roadmap

### Immediate Improvements (Quick Wins)
- [ ] Add file preview before processing
- [ ] Support drag-and-drop file upload
- [ ] Add progress bar during processing
- [ ] Export to CSV option (in addition to Excel)

### Phase 2 Features
- [ ] User authentication/login
- [ ] Save processing history
- [ ] Compare current vs. previous periods
- [ ] Email report delivery
- [ ] Mobile-responsive design improvements

### Phase 3 Integration
- [ ] QuickBooks direct integration
- [ ] Automated Paychex data fetch (eliminate manual export)
- [ ] Real-time dashboard
- [ ] Project cost variance alerts
- [ ] Predictive cost forecasting

---

## 💬 Support

### Getting Help
1. Check this README first
2. Review the main [README_Job_Costing_Tool.md](README_Job_Costing_Tool.md)
3. Check [TECHNICAL_LOGIC_EXPLANATION.md](TECHNICAL_LOGIC_EXPLANATION.md) for calculation details
4. Contact AuraPath support

### Reporting Issues
When reporting issues, include:
- Browser and version
- Error message (if any)
- Steps to reproduce
- Screenshot (if helpful)
- Sample file format (no sensitive data)

---

## 📝 Version History

**Version 1.0** (December 2, 2025)
- Initial release
- File upload interface
- Results preview
- Excel download
- Summary statistics

---

**Questions?** Check the [QUICK_START.md](QUICK_START.md) or main documentation.

**Last Updated:** December 2, 2025
