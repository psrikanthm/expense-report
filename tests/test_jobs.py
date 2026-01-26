import os
import shutil
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from expense_report import jobs
from expense_report.models import Transaction, CategoryEnum, CategorizedTransaction, CategorizerEnum

# Define test resources path
TEST_RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")

@pytest.fixture
def temp_docs_dir(tmp_path):
    """
    Creates a temporary 'docs' directory structure for testing.
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "sources").mkdir()
    (docs_dir / "intermediate").mkdir()
    (docs_dir / "output").mkdir()
    return str(docs_dir)

def test_run_parse(temp_docs_dir):
    """
    Test that run_parse correctly reads from sources and writes to intermediate,
    using the base_dir argument.
    """
    # Setup: Copy sample amex.csv to temp sources
    shutil.copy(
        os.path.join(TEST_RESOURCES_DIR, "amex.csv"),
        os.path.join(temp_docs_dir, "sources", "amex.csv")
    )

    # Execute
    output_file = jobs.run_parse("2025-01", base_dir=temp_docs_dir)

    # Verify
    assert os.path.exists(output_file)
    assert "transactions_2025-01.csv" in output_file
    
    df = pd.read_csv(output_file)
    assert len(df) == 3
    assert df.iloc[0]['description'] == "AMAZON.CA"

def test_run_categorize(temp_docs_dir):
    """
    Test that run_categorize reads from intermediate and writes categorized file.
    """
    # Setup: Copy sample transactions file
    shutil.copy(
        os.path.join(TEST_RESOURCES_DIR, "transactions_2025-01.csv"),
        os.path.join(temp_docs_dir, "intermediate", "transactions_2025-01.csv")
    )

    # Execute
    # Mocking LLMCategorizer to avoid actual API calls during test (optional but good for speed/reliability)
    with patch('expense_report.jobs.LLMCategorizer') as MockLLM:
        mock_instance = MockLLM.return_value
        mock_instance.categorize.side_effect = lambda t: CategorizedTransaction(
            date=t.date, description=t.description, amount=t.amount, 
            category=CategoryEnum.UNCATEGORIZED, categorizer=CategorizerEnum.LLM
        )
        
        output_file = jobs.run_categorize("2025-01", base_dir=temp_docs_dir)

    # Verify
    assert os.path.exists(output_file)
    assert "categorized_2025-01.csv" in output_file
    
    df = pd.read_csv(output_file)
    assert len(df) == 3

def test_run_report_combines_history(temp_docs_dir):
    """
    Test that run_report passes current AND historical data to the report generator.
    """
    # Setup: Prepare current month and historical months in intermediate dir
    target_month = "2025-01"
    
    # 1. Current month (Jan 2025) - create a dummy categorized file directly
    current_csv = os.path.join(temp_docs_dir, "intermediate", f"categorized_{target_month}.csv")
    pd.DataFrame({
        "date": ["2025-01-05"], "description": ["Current"], "amount": [10.0],
        "category": ["GROCERIES"], "categorizer": ["KEYWORD"]
    }).to_csv(current_csv, index=False)
    
    # 2. Historical month 1 (Dec 2024)
    shutil.copy(
        os.path.join(TEST_RESOURCES_DIR, "categorized_2024-12.csv"),
        os.path.join(temp_docs_dir, "intermediate", "categorized_2024-12.csv")
    )
    
    # 3. Historical month 2 (Nov 2024)
    shutil.copy(
        os.path.join(TEST_RESOURCES_DIR, "categorized_2024-11.csv"),
        os.path.join(temp_docs_dir, "intermediate", "categorized_2024-11.csv")
    )

    # Mock ReportGenerator to verify what transactions are passed to it
    with patch('expense_report.reports.ReportGenerator') as MockGenerator:
        mock_gen_instance = MockGenerator.return_value
        mock_gen_instance.generate_report.return_value = os.path.join(temp_docs_dir, "output", f"report_{target_month}.pdf")
        
        # Execute
        jobs.run_report(target_month, base_dir=temp_docs_dir)
        
        # Verify
        assert mock_gen_instance.generate_report.called
        call_args = mock_gen_instance.generate_report.call_args
        transactions_passed = call_args[0][0] # First arg is transactions list
        month_passed = call_args[0][1]
        
        assert month_passed == target_month
        
        # Check that we have transactions from all 3 months
        # We expect: 
        # Jan 2025: 1 txn
        # Dec 2024: 2 txn (from resource file)
        # Nov 2024: 1 txn (from resource file)
        # Total: 4
        assert len(transactions_passed) == 4
        
        dates = sorted([t.date.strftime("%Y-%m-%d") for t in transactions_passed])
        assert "2025-01-05" in dates
        assert "2024-12-15" in dates
        assert "2024-11-05" in dates

def test_run_report_no_history(temp_docs_dir):
    """
    Test run_report when no history exists.
    """
    target_month = "2025-01"
    current_csv = os.path.join(temp_docs_dir, "intermediate", f"categorized_{target_month}.csv")
    pd.DataFrame({
        "date": ["2025-01-05"], "description": ["Current"], "amount": [10.0],
        "category": ["GROCERIES"], "categorizer": ["KEYWORD"]
    }).to_csv(current_csv, index=False)

    with patch('expense_report.reports.ReportGenerator') as MockGenerator:
        mock_gen_instance = MockGenerator.return_value
        
        jobs.run_report(target_month, base_dir=temp_docs_dir)
        
        transactions_passed = mock_gen_instance.generate_report.call_args[0][0]
        assert len(transactions_passed) == 1
        assert transactions_passed[0].description == "Current"

