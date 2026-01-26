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
    (docs_dir / "reports").mkdir()
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

def test_run_render_pdf_combines_history(temp_docs_dir):
    """
    Test that run_render_pdf passes current AND historical data to the report generator.
    """
    # Setup: Prepare current month and historical months in intermediate and gold dirs
    target_month = "2025-01"
    
    # 1. Current month (Jan 2025)
    # Intermediate (Details)
    current_csv = os.path.join(temp_docs_dir, "intermediate", f"categorized_{target_month}.csv")
    pd.DataFrame({
        "date": ["2025-01-05"], "description": ["Current"], "amount": [10.0],
        "category": ["GROCERIES"], "categorizer": ["KEYWORD"]
    }).to_csv(current_csv, index=False)
    
    # Output (Aggregates) (formerly gold)
    output_dir = os.path.join(temp_docs_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    current_gold = os.path.join(output_dir, f"monthly_{target_month}.csv")
    pd.DataFrame({
        "category": ["GROCERIES"], "amount": [10.0]
    }).to_csv(current_gold, index=False)
    
    # 2. Historical month 1 (Dec 2024)
    # Aggregates must exist for history to be picked up
    hist1_gold = os.path.join(output_dir, f"monthly_2024-12.csv")
    pd.DataFrame({
        "category": ["UTILITY"], "amount": [50.0]
    }).to_csv(hist1_gold, index=False)
    
    # 3. Historical month 2 (Nov 2024)
    hist2_gold = os.path.join(output_dir, f"monthly_2024-11.csv")
    pd.DataFrame({
        "category": ["CAR"], "amount": [100.0]
    }).to_csv(hist2_gold, index=False)

    # Mock ReportGenerator to verify what transactions are passed to it
    with patch('expense_report.reports.ReportGenerator') as MockGenerator:
        mock_gen_instance = MockGenerator.return_value
        mock_gen_instance.generate_report.return_value = os.path.join(temp_docs_dir, "reports", f"report_{target_month}.pdf")
        
        # Execute
        jobs.run_render_pdf(target_month, base_dir=temp_docs_dir)
        
        # Verify
        assert mock_gen_instance.generate_report.called
        call_args = mock_gen_instance.generate_report.call_args
        
        # New signature: current_aggregates, historical_aggregates, transaction_details, month
        curr_agg = call_args.kwargs.get('current_aggregates')
        hist_agg = call_args.kwargs.get('historical_aggregates')
        
        if curr_agg is None: # Positional fallback
            curr_agg = call_args[0][0]
            hist_agg = call_args[0][1]
        
        assert len(curr_agg) == 1
        # Hist agg should contain current month (1 row) + 2 historical months (1 row each) = 3 rows total?
        # Logic in run_report: all_aggregates = [current_aggregates] + history loop
        # So yes, current is included in history DF passed to report generator (for trend chart continuity)
        assert len(hist_agg) == 3

def test_run_render_pdf_no_history(temp_docs_dir):
    """
    Test run_render_pdf when no history exists.
    """
    target_month = "2025-01"
    
    # Intermediate
    current_csv = os.path.join(temp_docs_dir, "intermediate", f"categorized_{target_month}.csv")
    pd.DataFrame({
        "date": ["2025-01-05"], "description": ["Current"], "amount": [10.0],
        "category": ["GROCERIES"], "categorizer": ["KEYWORD"]
    }).to_csv(current_csv, index=False)
    
    # Output (formerly Gold)
    output_dir = os.path.join(temp_docs_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    current_gold = os.path.join(output_dir, f"monthly_{target_month}.csv")
    pd.DataFrame({
        "category": ["GROCERIES"], "amount": [10.0]
    }).to_csv(current_gold, index=False)

    with patch('expense_report.reports.ReportGenerator') as MockGenerator:
        mock_gen_instance = MockGenerator.return_value
        
        jobs.run_render_pdf(target_month, base_dir=temp_docs_dir)
        
        call_args = mock_gen_instance.generate_report.call_args
        curr_agg = call_args.kwargs.get('current_aggregates') 
        if curr_agg is None: curr_agg = call_args[0][0]
        
        assert len(curr_agg) == 1
        assert curr_agg.iloc[0]['category'] == "GROCERIES"

