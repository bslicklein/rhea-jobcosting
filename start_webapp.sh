#!/bin/bash

# Job Costing Web App Startup Script
# Rhea Engineering - AuraPath

echo "=========================================="
echo "Job Costing Automation Tool - Web Interface"
echo "=========================================="
echo ""

# Navigate to script directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    # Activate virtual environment
    source venv/bin/activate
fi

echo "✓ Virtual environment activated"
echo ""

# Check if dependencies are installed
echo "Checking dependencies..."
python -c "import flask, pandas, openpyxl" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing missing dependencies..."
    pip install -r requirements.txt
fi

echo "✓ All dependencies installed"
echo ""

# Start the Flask app
echo "Starting web server..."
echo ""
echo "=========================================="
echo "🚀 Server starting at http://127.0.0.1:5001"
echo "=========================================="
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

python app.py
