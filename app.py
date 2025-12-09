from flask import Flask, render_template, request, send_file, jsonify, session
import pandas as pd
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import tempfile
import sys
from io import StringIO
import pickle
from job_costing_converter import process_paychex_files, detect_overtime_and_prepare_selection
from employee_master import (
    load_employees, save_employees, get_employee_list, 
    update_employee, delete_employee, bulk_update_employees, Employee
)

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()
app.config['SECRET_KEY'] = 'rhea-job-costing-secret-key-change-in-production'

ALLOWED_EXTENSIONS = {'txt', 'csv', 'xlsx', 'xls'}

# Store temp data for OT allocation (in production, use Redis or database)
temp_storage = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    try:
        # Check if files were uploaded
        if 'week1File' not in request.files or 'week2File' not in request.files:
            return jsonify({'error': 'Both week 1 and week 2 files are required'}), 400

        week1_file = request.files['week1File']
        week2_file = request.files['week2File']

        # Validate files
        if week1_file.filename == '' or week2_file.filename == '':
            return jsonify({'error': 'Both files must be selected'}), 400

        if not (allowed_file(week1_file.filename) and allowed_file(week2_file.filename)):
            return jsonify({'error': 'Invalid file type. Allowed types: .txt, .csv, .xlsx, .xls'}), 400

        # Save uploaded files
        week1_filename = secure_filename(week1_file.filename)
        week2_filename = secure_filename(week2_file.filename)

        week1_path = os.path.join(app.config['UPLOAD_FOLDER'], f"week1_{datetime.now().timestamp()}_{week1_filename}")
        week2_path = os.path.join(app.config['UPLOAD_FOLDER'], f"week2_{datetime.now().timestamp()}_{week2_filename}")

        week1_file.save(week1_path)
        week2_file.save(week2_path)

        # Debug: Log file info
        print(f"\n[DEBUG] Files saved:")
        print(f"  Week 1: {week1_path} ({os.path.getsize(week1_path)} bytes)")
        print(f"  Week 2: {week2_path} ({os.path.getsize(week2_path)} bytes)")

        # Debug: Check file columns
        try:
            import pandas as pd
            df_test = pd.read_excel(week1_path) if week1_path.endswith('.xlsx') else pd.read_csv(week1_path, sep='\t')
            print(f"  Week 1 columns: {df_test.columns.tolist()}")
        except Exception as e:
            print(f"  Warning: Could not read Week 1 preview: {e}")

        # PHASE 1: Detect overtime situations
        ot_data, temp_df = detect_overtime_and_prepare_selection(week1_path, week2_path)

        if ot_data is None:
            os.remove(week1_path)
            os.remove(week2_path)
            return jsonify({'error': 'Failed to process files'}), 500

        # If there's overtime, store files and return OT selection UI data
        if ot_data['has_overtime']:
            # Generate unique session ID
            session_id = f"session_{datetime.now().timestamp()}"

            # Store file paths and data for phase 2
            temp_storage[session_id] = {
                'week1_path': week1_path,
                'week2_path': week2_path,
                'timestamp': datetime.now()
            }

            return jsonify({
                'requires_ot_selection': True,
                'session_id': session_id,
                'ot_data': ot_data
            }), 200

        # No overtime - process normally
        output_filename = f"job_costing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            summary, totals, unknown_employees = process_paychex_files(week1_path, week2_path, output_path)
        except Exception as e:
            sys.stdout = old_stdout
            if os.path.exists(week1_path):
                os.remove(week1_path)
            if os.path.exists(week2_path):
                os.remove(week2_path)
            raise e
        finally:
            sys.stdout = old_stdout

        os.remove(week1_path)
        os.remove(week2_path)

        # Check if there are unknown employees that need to be added to roster
        if unknown_employees:
            return jsonify({
                'requires_roster_update': True,
                'unknown_employees': unknown_employees,
                'message': f'Found {len(unknown_employees)} employee(s) not in the roster. Please add them before processing.'
            }), 200

        if summary is None or totals is None:
            processing_log = captured_output.getvalue()
            return jsonify({'error': f'Failed to process files. Processing log: {processing_log}'}), 500

        summary_data = summary.to_dict('records')
        totals_data = totals.to_dict('records')

        response = {
            'success': True,
            'message': 'Files processed successfully',
            'outputFile': output_filename,
            'outputPath': output_path,
            'summary': summary_data[:10],  # First 10 rows for preview
            'totals': totals_data,
            'totalRecords': len(summary_data)
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({'error': f'Processing error: {str(e)}'}), 500

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        return jsonify({'error': f'Download error: {str(e)}'}), 500

@app.route('/process_with_ot_selections', methods=['POST'])
def process_with_ot_selections():
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        ot_allocations = data.get('ot_allocations')

        if not session_id or session_id not in temp_storage:
            return jsonify({'error': 'Invalid or expired session'}), 400

        # Retrieve stored file paths
        session_data = temp_storage[session_id]
        week1_path = session_data['week1_path']
        week2_path = session_data['week2_path']

        # Verify files still exist
        if not os.path.exists(week1_path) or not os.path.exists(week2_path):
            del temp_storage[session_id]
            return jsonify({'error': 'Uploaded files have expired'}), 400

        # PHASE 2: Process with user-selected OT allocations
        output_filename = f"job_costing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            summary, totals, unknown_employees = process_paychex_files(week1_path, week2_path, output_path, ot_allocations=ot_allocations)
        except Exception as e:
            sys.stdout = old_stdout
            if os.path.exists(week1_path):
                os.remove(week1_path)
            if os.path.exists(week2_path):
                os.remove(week2_path)
            del temp_storage[session_id]
            raise e
        finally:
            sys.stdout = old_stdout

        # Check if there are unknown employees that need to be added to roster
        if unknown_employees:
            # Don't delete files yet - user needs to add employees and retry
            return jsonify({
                'requires_roster_update': True,
                'unknown_employees': unknown_employees,
                'session_id': session_id,  # Keep session for retry
                'message': f'Found {len(unknown_employees)} employee(s) not in the roster. Please add them before processing.'
            }), 200

        # Clean up temp files and session
        os.remove(week1_path)
        os.remove(week2_path)
        del temp_storage[session_id]

        if summary is None or totals is None:
            processing_log = captured_output.getvalue()
            return jsonify({'error': f'Failed to process files. Processing log: {processing_log}'}), 500

        summary_data = summary.to_dict('records')
        totals_data = totals.to_dict('records')

        response = {
            'success': True,
            'message': 'Files processed successfully with OT allocations',
            'outputFile': output_filename,
            'outputPath': output_path,
            'summary': summary_data[:10],
            'totals': totals_data,
            'totalRecords': len(summary_data)
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({'error': f'Processing error: {str(e)}'}), 500

@app.route('/preview/<filename>')
def preview_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404

        # Read all sheets
        excel_file = pd.ExcelFile(file_path)
        sheets = {}

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            sheets[sheet_name] = df.to_dict('records')

        return jsonify({'sheets': sheets}), 200

    except Exception as e:
        return jsonify({'error': f'Preview error: {str(e)}'}), 500

# Employee Roster Management Routes
@app.route('/api/roster', methods=['GET'])
def get_roster():
    """Get all employees in the roster"""
    try:
        employees = get_employee_list()
        return jsonify({'success': True, 'employees': employees}), 200
    except Exception as e:
        return jsonify({'error': f'Error loading roster: {str(e)}'}), 500

@app.route('/api/roster', methods=['POST'])
def add_employee():
    """Add a new employee to the roster"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Employee name is required'}), 400
        if not data.get('employee_type') or data.get('employee_type') not in ['hourly', 'salaried']:
            return jsonify({'error': 'Employee type must be "hourly" or "salaried"'}), 400
        if not data.get('base_rate') or float(data.get('base_rate', 0)) <= 0:
            return jsonify({'error': 'Valid base rate is required'}), 400

        success = update_employee(
            name=data['name'],
            employee_type=data['employee_type'],
            base_rate=float(data['base_rate']),
            qb_indirect_code=data.get('qb_indirect_code', ''),
            qb_direct_code=data.get('qb_direct_code', '')
        )

        if success:
            return jsonify({'success': True, 'message': 'Employee added successfully'}), 200
        else:
            return jsonify({'error': 'Failed to save employee'}), 500
    except Exception as e:
        return jsonify({'error': f'Error adding employee: {str(e)}'}), 500

@app.route('/api/roster/update', methods=['PUT'])
def update_employee_route():
    """Update an existing employee"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Employee name is required'}), 400
        if not data.get('original_name'):
            return jsonify({'error': 'Original employee name is required'}), 400
        if not data.get('employee_type') or data.get('employee_type') not in ['hourly', 'salaried']:
            return jsonify({'error': 'Employee type must be "hourly" or "salaried"'}), 400
        if not data.get('base_rate') or float(data.get('base_rate', 0)) <= 0:
            return jsonify({'error': 'Valid base rate is required'}), 400

        original_name = data['original_name']
        new_name = data['name']
        
        # If name changed, we need to delete old and create new
        employees = load_employees()
        if original_name in employees and new_name != original_name:
            # Delete old entry
            del employees[original_name]
            save_employees(employees)

        success = update_employee(
            name=new_name,
            employee_type=data['employee_type'],
            base_rate=float(data['base_rate']),
            qb_indirect_code=data.get('qb_indirect_code', ''),
            qb_direct_code=data.get('qb_direct_code', '')
        )

        if success:
            return jsonify({'success': True, 'message': 'Employee updated successfully'}), 200
        else:
            return jsonify({'error': 'Failed to update employee'}), 500
    except Exception as e:
        return jsonify({'error': f'Error updating employee: {str(e)}'}), 500

@app.route('/api/roster/delete', methods=['POST'])
def delete_employee_route():
    """Delete an employee from the roster"""
    try:
        data = request.get_json()
        employee_name = data.get('name')
        
        if not employee_name:
            return jsonify({'error': 'Employee name is required'}), 400
            
        success = delete_employee(employee_name)
        if success:
            return jsonify({'success': True, 'message': 'Employee deleted successfully'}), 200
        else:
            return jsonify({'error': 'Employee not found or failed to delete'}), 404
    except Exception as e:
        return jsonify({'error': f'Error deleting employee: {str(e)}'}), 500

@app.route('/api/roster/bulk', methods=['POST'])
def bulk_update_roster():
    """Bulk update multiple employees (for importing/updating from spreadsheet)"""
    try:
        data = request.get_json()
        employees_data = data.get('employees', [])
        
        if not employees_data:
            return jsonify({'error': 'No employee data provided'}), 400

        success = bulk_update_employees(employees_data)
        
        if success:
            return jsonify({'success': True, 'message': f'Updated {len(employees_data)} employees'}), 200
        else:
            return jsonify({'error': 'Failed to update employees'}), 500
    except Exception as e:
        return jsonify({'error': f'Error bulk updating: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
