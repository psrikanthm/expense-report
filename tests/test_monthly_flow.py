import os
import shutil
import pytest
import pandas as pd
from unittest.mock import patch, MagicMock
from expense_report import jobs

# Copied from test_jobs.py
@pytest.fixture
def temp_docs_dir(tmp_path):
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "sources").mkdir()
    (docs_dir / "intermediate").mkdir()
    (docs_dir / "output").mkdir()
    return str(docs_dir)

def test_run_aggregate_aggregates(temp_docs_dir):
    """
    Test that run_aggregate aggregates data and filters excluded categories.
    """
    month = "2025-01"
    
    # 1. Setup Categorized CSV
    # Create transactions: 
    # - 2 Groceries
    # - 1 Transfer (should be excluded)
    # - 1 Restaurant
    transactions_df = pd.DataFrame({
        "date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
        "description": ["Store A", "Store B", "Transfer Out", "Cafe"],
        "amount": [50.0, 30.0, 100.0, 15.0],
        "category": ["GROCERIES", "GROCERIES", "TRANSFER", "RESTAURANTS"],
        "categorizer": ["KEYWORD", "KEYWORD", "KEYWORD", "KEYWORD"]
    })
    
    intermediate_file = os.path.join(temp_docs_dir, "intermediate", f"categorized_{month}.csv")
    transactions_df.to_csv(intermediate_file, index=False)
    
    # 2. Mock _load_categories to force 'TRANSFER' exclusion
    # We mock jobs._load_categories if imported there, or where needed.
    # The logic is inside jobs.run_monthly_data which imports from .models.
    
    mock_categories = [
        {"name": "groceries"},
        {"name": "restaurants"},
        {"name": "transfer", "report_excluded": True}
    ]
    
    with patch('expense_report.models._load_categories', return_value=mock_categories):
        output_file = jobs.run_aggregate(month, base_dir=temp_docs_dir)
        
    # 3. Verify
    assert os.path.exists(output_file)
    assert f"monthly_{month}.csv" in output_file
    
    gold_df = pd.read_csv(output_file)
    
    # Expected: TRANSFER is gone. GROCERIES aggregated. RESTAURANTS present.
    assert "TRANSFER" not in gold_df['category'].values
    
    groceries = gold_df[gold_df['category'] == "GROCERIES"].iloc[0]
    assert groceries['amount'] == 80.0 # 50 + 30
    
    restaurants = gold_df[gold_df['category'] == "RESTAURANTS"].iloc[0]
    assert restaurants['amount'] == 15.0
    
    assert len(gold_df) == 2

def test_run_parse_dedupes(temp_docs_dir):
    """
    Test that run_parse drops exact duplicates.
    """
    # Assuming run_parse calls parsers. We mock parsers returning duplicates.
    
    month = "2025-01"
    
    from expense_report.models import Transaction
    import datetime
    
    # Duplicate transaction list
    t1 = Transaction(date=datetime.date(2025,1,1), description="Dup", amount=10.0)
    t2 = Transaction(date=datetime.date(2025,1,1), description="Dup", amount=10.0)
    t3 = Transaction(date=datetime.date(2025,1,2), description="Unique", amount=20.0)
    
    mock_transactions = [t1, t2, t3]
    
    # Mock one parser to return these
    with patch('expense_report.jobs.AmexParser') as MockAmex, \
         patch('expense_report.jobs.CibcParser') as MockCibc, \
         patch('expense_report.jobs.ScotiaParser') as MockScotia:
             
        mock_amex_instance = MockAmex.return_value
        # Mock file existence for amex only
        with patch('os.path.exists') as mock_exists:
             # We need to allow os.path.exists to work for dir creation too... this is tricky with global mock.
             # Easier to just rely on the fact the code checks for specific source files.
             # Let's side_effect the exists check.
             def side_effect(path):
                 if "amex.csv" in path: return True
                 if "docs" in path: return True # allow dir checks
                 return False
                 
             mock_exists.side_effect = side_effect
             
             mock_amex_instance.parse.return_value = mock_transactions
             
             # Need to ensure intermediate dir exists since we mocked os.path.exists? 
             # No, os.makedirs is different.
             # But run_parse calls _ensure_directories which might check things.
             # Actually, simpler approach: create a dummy amex.csv and let the real parser work? 
             # Or just patch methods on the parser instances returned by keys in the list.
             
             # The code loop: for parser, file_path in parsers: ... if os.path.exists(file_path)
             # Let's create the dummy file physically.
             source_file = os.path.join(temp_docs_dir, "sources", "amex.csv")
             with open(source_file, 'w') as f:
                 f.write("dummy") # Content doesn't matter if we mock .parse()
             
             mock_amex_instance.parse.return_value = mock_transactions
             
             output_file = jobs.run_parse(month, base_dir=temp_docs_dir)
             
    df = pd.read_csv(output_file)
    assert len(df) == 2 # 3 transactions, 1 duplicate removed = 2 unique
    assert df[df['description'] == 'Dup']['amount'].sum() == 10.0

def test_run_aggregate_safety_dedupe(temp_docs_dir):
    """
    Test that run_aggregate performs a second pass of deduplication.
    """
    month = "2025-01"
    
    # 1. Setup Categorized CSV with duplicates (simulating an issue upstream)
    transactions_df = pd.DataFrame({
        "date": ["2025-01-01", "2025-01-01", "2025-01-02"],
        "description": ["Store A", "Store A", "Store B"],
        "amount": [50.0, 50.0, 30.0],
        "category": ["GROCERIES", "GROCERIES", "GROCERIES"],
        "categorizer": ["KEYWORD", "KEYWORD", "KEYWORD"]
    })
    
    intermediate_file = os.path.join(temp_docs_dir, "intermediate", f"categorized_{month}.csv")
    transactions_df.to_csv(intermediate_file, index=False)
    
    # 2. Run monthly data
    # Mock categories to avoid needing the real file
    mock_categories = [{"name": "groceries"}]
    
    with patch('expense_report.models._load_categories', return_value=mock_categories):
        output_file = jobs.run_aggregate(month, base_dir=temp_docs_dir)
        
    # 3. Verify Aggregates
    gold_df = pd.read_csv(output_file)
    
    # If dedupe worked, Store A counted once (50) + Store B (30) = 80 total
    # If dedupe failed, Store A counted twice (100) + Store B (30) = 130 total
    
    groceries = gold_df[gold_df['category'] == "GROCERIES"].iloc[0]
    assert groceries['amount'] == 80.0
