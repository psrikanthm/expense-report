import os
import tempfile
import pandas as pd
import pytest
from pathlib import Path
from expense_report.reports import ReportGenerator

def test_generate_report_creates_pdf_with_averages():
    # Setup dummy data
    month = "2025-01"
    
    current_aggregates = pd.DataFrame([
        {"category": "GROCERIES", "amount": 120.50},
        {"category": "RESTAURANTS", "amount": 45.00},
        {"category": "TRANSPORTATION", "amount": 35.00}
    ])
    
    # Historical aggregates for past 6 months to trigger the averages calculation
    historical_aggregates = pd.DataFrame([
        {"category": "GROCERIES", "amount": 100.00, "date": "2024-08-01"},
        {"category": "RESTAURANTS", "amount": 50.00, "date": "2024-08-01"},
        {"category": "GROCERIES", "amount": 110.00, "date": "2024-09-01"},
        {"category": "GROCERIES", "amount": 90.00, "date": "2024-10-01"},
        {"category": "GROCERIES", "amount": 130.00, "date": "2024-11-01"},
        {"category": "RESTAURANTS", "amount": 60.00, "date": "2024-11-01"},
        {"category": "GROCERIES", "amount": 115.00, "date": "2024-12-01"},
        {"category": "GROCERIES", "amount": 120.50, "date": "2025-01-01"},
        {"category": "RESTAURANTS", "amount": 45.00, "date": "2025-01-01"},
        {"category": "TRANSPORTATION", "amount": 35.00, "date": "2025-01-01"},
    ])
    
    transaction_details = pd.DataFrame([
        {"date": "2025-01-05", "description": "Supermarket", "amount": 80.50, "category": "GROCERIES"},
        {"date": "2025-01-10", "description": "Local Store", "amount": 40.00, "category": "GROCERIES"},
        {"date": "2025-01-12", "description": "Diner", "amount": 45.00, "category": "RESTAURANTS"},
        {"date": "2025-01-15", "description": "Bus ticket", "amount": 35.00, "category": "TRANSPORTATION"},
    ])
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        generator = ReportGenerator(output_dir=tmp_dir)
        report_path = generator.generate_report(
            current_aggregates=current_aggregates,
            historical_aggregates=historical_aggregates,
            transaction_details=transaction_details,
            month=month
        )
        
        # Verify the file was created and is non-empty
        assert report_path is not None
        assert os.path.exists(report_path)
        assert os.path.getsize(report_path) > 0
        assert report_path.name == f"report_{month}.pdf"

def test_generate_report_handles_empty_history():
    month = "2025-01"
    
    current_aggregates = pd.DataFrame([
        {"category": "GROCERIES", "amount": 120.50}
    ])
    
    historical_aggregates = pd.DataFrame(columns=["category", "amount", "date"])
    
    transaction_details = pd.DataFrame([
        {"date": "2025-01-05", "description": "Supermarket", "amount": 120.50, "category": "GROCERIES"}
    ])
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        generator = ReportGenerator(output_dir=tmp_dir)
        report_path = generator.generate_report(
            current_aggregates=current_aggregates,
            historical_aggregates=historical_aggregates,
            transaction_details=transaction_details,
            month=month
        )
        
        assert report_path is not None
        assert os.path.exists(report_path)
        assert os.path.getsize(report_path) > 0
